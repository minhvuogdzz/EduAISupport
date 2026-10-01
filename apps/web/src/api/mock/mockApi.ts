/**
 * In-browser implementation of SessionApi, used until the session API of T08 exists.
 *
 * It behaves like the server should: SessionContext checks (PART 24.2), idempotency keys, optimistic
 * concurrency on state_version, one atomic write of state + events per command, and a stream of
 * tutor.delta / tutor.final / state events (PART 29.3). The tutoring itself is a mock (engine.ts).
 */
import { newId } from "../../lib/ids";
import { ApiError, type SessionApi } from "../client";
import type { CommandAck, CommandType, SessionState, StreamEvent } from "../contract";
import {
  allowedCommands,
  applyCommand,
  newSession,
  startSession,
  type EngineContext,
  type MockCommand,
  type MockSession,
} from "./engine";
import { LESSON } from "./lesson";
import type { LessonPackage } from "./lessonTypes";
import { HINT_CHOICES } from "./phrases";
import { seedSessions } from "./seed";
import { browserStorage, createStore, type MockDb } from "./store";
import { toState, toSummary, toTranscript } from "./views";

export interface MockApiOptions {
  lesson?: LessonPackage;
  /** Where demo data persists. Default: localStorage when usable. null: memory only. */
  storage?: Storage | null;
  now?: () => Date;
  newId?: () => string;
  /** Simulated network latency of every call, in ms. */
  latencyMs?: number;
  /** Delay between the streamed words of a tutor turn, in ms. */
  typingDelayMs?: number;
  /** Seed the demo sessions of seed.ts when the store is empty. */
  seed?: boolean;
}

const MAX_TEXT_LENGTH = 500;
const MAX_NAME_LENGTH = 30;

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
const clone = (session: MockSession) => JSON.parse(JSON.stringify(session)) as MockSession;

export function createMockApi(options: MockApiOptions = {}): SessionApi {
  const lesson = options.lesson ?? LESSON;
  const ctx: EngineContext = {
    lesson,
    now: options.now ?? (() => new Date()),
    newId: options.newId ?? newId,
  };
  const store = createStore(options.storage === undefined ? browserStorage() : options.storage);
  const latencyMs = options.latencyMs ?? 150;
  const typingDelayMs = options.typingDelayMs ?? 45;
  const seed = options.seed ?? true;
  const listeners = new Map<string, Set<(event: StreamEvent) => void>>();

  function load(): MockDb {
    const stored = store.read();
    if (stored) return stored;
    const db: MockDb = { schema: 1, sessions: seed ? seedSessions(lesson) : {}, acks: {} };
    store.write(db);
    return db;
  }

  function sessionIn(db: MockDb, sessionId: string): MockSession {
    const session = db.sessions[sessionId] as MockSession | undefined;
    if (!session) throw new ApiError(404, "NOT_FOUND", `session ${sessionId} not found`);
    return session;
  }

  function publish(sessionId: string, event: StreamEvent) {
    for (const listener of listeners.get(sessionId) ?? []) listener(event);
  }

  /** New tutor turns word by word (tutor.delta … tutor.final), then the new state. */
  async function stream(state: SessionState, turnIds: string[]) {
    for (const turnId of turnIds) {
      const turn = state.transcript.find((t) => t.turn_id === turnId);
      if (!turn) continue;
      for (const word of turn.text.match(/\S+\s*/g) ?? []) {
        await sleep(typingDelayMs);
        publish(state.session_id, { event: "tutor.delta", data: { turn_id: turnId, delta: word } });
      }
      publish(state.session_id, { event: "tutor.final", data: turn });
    }
    publish(state.session_id, { event: "state", data: state });
  }

  /** SessionContext checks, then one atomic write of state + events (PART 24.2, 16.4). */
  async function command(
    sessionId: string,
    idempotencyKey: string,
    expectedVersion: number,
    type: CommandType,
    itemAttemptId: string | null,
    mockCommand: MockCommand,
  ): Promise<CommandAck> {
    await sleep(latencyMs);
    const db = load();
    const session = sessionIn(db, sessionId);
    // A retried command gets its first result back, even though the state moved on since.
    const replay = db.acks[`${sessionId}:${idempotencyKey}`] as CommandAck | undefined;
    if (replay) return replay;
    if (session.lifecycle_state !== "ACTIVE") {
      throw new ApiError(409, "INVALID_STATE", `session is ${session.lifecycle_state}`);
    }
    if (itemAttemptId !== null && session.item?.item_attempt_id !== itemAttemptId) {
      throw new ApiError(409, "STALE_ITEM", "the item is no longer the current one");
    }
    if (expectedVersion !== session.state_version) {
      throw new ApiError(409, "STATE_VERSION_CONFLICT", "the session changed since the client read it", {
        state_version: session.state_version,
      });
    }
    if (!allowedCommands(session).includes(type)) {
      throw new ApiError(409, "COMMAND_NOT_ALLOWED_IN_ACTIVITY", `${type} is not allowed now`);
    }
    const next = clone(session);
    const turnIds = applyCommand(ctx, next, mockCommand, idempotencyKey);
    const ack: CommandAck = {
      accepted: true,
      state_version: next.state_version,
      tutor_turn_id: turnIds[0] ?? null,
    };
    db.sessions[sessionId] = next;
    db.acks[`${sessionId}:${idempotencyKey}`] = ack;
    store.write(db);
    void stream(toState(next, lesson), turnIds);
    return ack;
  }

  return {
    engine: "mock",

    async createDemoSession({ student_display_name }) {
      const name = student_display_name.trim();
      if (!name || name.length > MAX_NAME_LENGTH) {
        throw new ApiError(
          400,
          "VALIDATION_ERROR",
          `student_display_name must be 1–${MAX_NAME_LENGTH} characters`,
        );
      }
      await sleep(latencyMs);
      const db = load();
      const session = newSession(ctx, name);
      db.sessions[session.session_id] = session;
      store.write(db);
      return { session_id: session.session_id };
    },

    async getState(sessionId) {
      await sleep(latencyMs);
      return toState(sessionIn(load(), sessionId), lesson);
    },

    async join(sessionId) {
      await sleep(latencyMs);
      const db = load();
      const session = sessionIn(db, sessionId);
      if (session.lifecycle_state === "READY") {
        const next = clone(session);
        startSession(ctx, next);
        db.sessions[sessionId] = next;
        store.write(db);
        return toState(next, lesson);
      }
      if (session.lifecycle_state === "ACTIVE" || session.lifecycle_state === "COMPLETED") {
        return toState(session, lesson); // rejoin = resume (PART 24.4)
      }
      throw new ApiError(409, "INVALID_STATE", `cannot join a session that is ${session.lifecycle_state}`);
    },

    submitResponse(sessionId, cmd, idempotencyKey) {
      if (cmd.content.text.length > MAX_TEXT_LENGTH) {
        return Promise.reject(
          new ApiError(400, "VALIDATION_ERROR", `text is longer than ${MAX_TEXT_LENGTH}`),
        );
      }
      return command(sessionId, idempotencyKey, cmd.expected_state_version, "ANSWER", cmd.item_attempt_id, {
        type: "ANSWER",
        kind: cmd.kind,
        text: cmd.content.text,
        modality: cmd.modality,
      });
    },

    requestHint(sessionId, cmd, idempotencyKey) {
      return command(
        sessionId,
        idempotencyKey,
        cmd.expected_state_version,
        "HINT_REQUEST",
        cmd.item_attempt_id,
        {
          type: "HINT_REQUEST",
        },
      );
    },

    choose(sessionId, cmd, idempotencyKey) {
      if (!HINT_CHOICES.some((c) => c.choice_id === cmd.choice_id)) {
        return Promise.reject(new ApiError(400, "VALIDATION_ERROR", `unknown choice ${cmd.choice_id}`));
      }
      return command(sessionId, idempotencyKey, cmd.expected_state_version, "CHOICE", null, {
        type: "CHOICE",
        choice_id: cmd.choice_id,
      });
    },

    subscribe(sessionId, onEvent) {
      const set = listeners.get(sessionId) ?? new Set();
      set.add(onEvent);
      listeners.set(sessionId, set);
      return () => {
        set.delete(onEvent);
      };
    },

    async listSessions() {
      await sleep(latencyMs);
      return Object.values(load().sessions)
        .map((session) => toSummary(session, lesson))
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    },

    async getTranscript(sessionId) {
      await sleep(latencyMs);
      // The real endpoint also writes an audit entry (TRANSCRIPT_VIEWED, PART 30.5).
      return toTranscript(sessionIn(load(), sessionId), lesson);
    },

    resetDemoData() {
      store.clear();
      return Promise.resolve();
    },
  };
}
