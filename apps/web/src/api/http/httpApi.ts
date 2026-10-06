/**
 * SessionApi over HTTP: the session API of services/api (T08, T13).
 *
 * The API has no SSE stream yet (GET /v1/sessions/{id}/stream), so `subscribe` is fed locally: after
 * every command this client reads GET /state and publishes the new tutor turns word by word, then the
 * state, in the same order the stream will use (tutor.delta … tutor.final, state). Screens do not change
 * when the real stream arrives.
 *
 * **Temporary identity (until T12):** the student is a random id kept in this browser and sent as
 * `X-Demo-Student`; teacher calls send `X-Demo-Teacher`. Neither is real authentication.
 */
import { newId } from "../../lib/ids";
import { ApiError, type SessionApi } from "../client";
import {
  API_ERROR_CODES,
  type ApiErrorCode,
  type ChatTurn,
  type ClassOverview,
  type CommandAck,
  type SessionState,
  type SessionSummary,
  type ParentChildView,
  type SessionTranscript,
  type StreamEvent,
  type StudentOverview,
  type TeachingReport,
  type TeacherStudentView,
} from "../contract";

export interface HttpApiOptions {
  /** Origin of the API. "" (default) uses the page's origin: the Vite dev server proxies /v1. */
  baseUrl?: string;
  fetch?: typeof fetch;
  /** Where the temporary demo identity is kept. Default: localStorage when usable. null: memory only. */
  storage?: Storage | null;
  /** Delay between the words of a new tutor turn, in ms. */
  typingDelayMs?: number;
  newId?: () => string;
}

const STUDENT_KEY = "cavat.demo.student-id";
const TEACHER_HEADERS = { "X-Demo-Teacher": "web" };
const PARENT_HEADERS = { "X-Demo-Parent": "web" };

function browserStorage(): Storage | null {
  try {
    return globalThis.localStorage;
  } catch {
    return null; // storage blocked: the identity then lasts until the page is reloaded
  }
}

function sleep(ms: number): Promise<void> {
  return ms > 0 ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve();
}

function isErrorCode(code: unknown): code is ApiErrorCode {
  return typeof code === "string" && (API_ERROR_CODES as readonly string[]).includes(code);
}

/** `{ error: { code, message, details } }` becomes an ApiError; anything else is a plain failure. */
async function toError(response: Response): Promise<Error> {
  try {
    const body = (await response.json()) as {
      error?: { code?: unknown; message?: unknown; details?: unknown };
    };
    const error = body.error;
    if (error && isErrorCode(error.code)) {
      const message = typeof error.message === "string" ? error.message : error.code;
      const details = (error.details ?? {}) as Record<string, unknown>;
      return new ApiError(response.status, error.code, message, details);
    }
  } catch {
    // not JSON (for example the dev proxy answering while the API is down)
  }
  return new Error(`HTTP ${response.status}`);
}

export function createHttpApi(options: HttpApiOptions = {}): SessionApi {
  const baseUrl = options.baseUrl ?? "";
  const doFetch = options.fetch ?? ((input, init) => globalThis.fetch(input, init));
  const typingDelayMs = options.typingDelayMs ?? 30;
  const makeId = options.newId ?? newId;
  const storage = options.storage === undefined ? browserStorage() : options.storage;

  const listeners = new Map<string, Set<(event: StreamEvent) => void>>();
  /** Highest sequence_no this client has already shown, per session: newer tutor turns are streamed. */
  const seen = new Map<string, number>();
  let memoryStudentId: string | null = null;

  function studentHeaders(): Record<string, string> {
    let id = memoryStudentId;
    try {
      id ??= storage?.getItem(STUDENT_KEY) ?? null;
      if (!id) {
        id = makeId();
        storage?.setItem(STUDENT_KEY, id);
      }
    } catch {
      id ??= makeId();
    }
    memoryStudentId = id;
    return { "X-Demo-Student": id };
  }

  async function request<T>(
    method: "GET" | "POST",
    path: string,
    headers: Record<string, string>,
    body?: unknown,
  ): Promise<T> {
    const response = await doFetch(`${baseUrl}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) throw await toError(response);
    return (await response.json()) as T;
  }

  function sessionPath(sessionId: string, tail: string): string {
    return `/v1/sessions/${encodeURIComponent(sessionId)}/${tail}`;
  }

  function remember(state: SessionState): SessionState {
    const last = state.transcript.at(-1)?.sequence_no ?? 0;
    seen.set(state.session_id, Math.max(seen.get(state.session_id) ?? 0, last));
    return state;
  }

  function publish(sessionId: string, event: StreamEvent) {
    for (const listener of listeners.get(sessionId) ?? []) listener(event);
  }

  /** New tutor turns word by word (tutor.delta … tutor.final), then the new state. */
  async function stream(state: SessionState, turns: ChatTurn[]) {
    for (const turn of turns) {
      for (const word of turn.text.match(/\S+\s*/g) ?? []) {
        await sleep(typingDelayMs);
        publish(state.session_id, { event: "tutor.delta", data: { turn_id: turn.turn_id, delta: word } });
      }
      publish(state.session_id, { event: "tutor.final", data: turn });
    }
    publish(state.session_id, { event: "state", data: state });
  }

  async function command(sessionId: string, tail: string, body: unknown, key: string): Promise<CommandAck> {
    const before = seen.get(sessionId);
    const headers = { ...studentHeaders(), "Idempotency-Key": key };
    const ack = await request<CommandAck>("POST", sessionPath(sessionId, tail), headers, body);
    // Read the state before answering: if this fails the command is rejected, the student sends again
    // and the 409 of that resend reloads the screen. Nothing waits for a stream that never comes.
    const state = await request<SessionState>("GET", sessionPath(sessionId, "state"), studentHeaders());
    const fresh =
      before === undefined
        ? []
        : state.transcript.filter((t) => t.actor === "tutor" && t.sequence_no > before);
    remember(state);
    void stream(state, fresh);
    return ack;
  }

  return {
    engine: "live",

    async createDemoSession(input) {
      const state = await request<SessionState>("POST", "/v1/sessions", studentHeaders(), input);
      return { session_id: state.session_id };
    },

    async getState(sessionId) {
      return remember(await request<SessionState>("GET", sessionPath(sessionId, "state"), studentHeaders()));
    },

    async join(sessionId) {
      return remember(await request<SessionState>("POST", sessionPath(sessionId, "join"), studentHeaders()));
    },

    submitResponse(sessionId, cmd, idempotencyKey) {
      return command(sessionId, "responses", cmd, idempotencyKey);
    },

    requestHint(sessionId, cmd, idempotencyKey) {
      return command(sessionId, "hint-requests", cmd, idempotencyKey);
    },

    choose(sessionId, cmd, idempotencyKey) {
      return command(sessionId, "choices", cmd, idempotencyKey);
    },

    subscribe(sessionId, onEvent) {
      const set = listeners.get(sessionId) ?? new Set();
      set.add(onEvent);
      listeners.set(sessionId, set);
      return () => {
        set.delete(onEvent);
      };
    },

    listMySessions() {
      return request<SessionSummary[]>("GET", "/v1/sessions/mine", studentHeaders());
    },

    getMyOverview() {
      return request<StudentOverview>("GET", "/v1/students/me/overview", studentHeaders());
    },

    getChildOverview(code) {
      return request<ParentChildView>(
        "GET",
        `/v1/parents/children/${encodeURIComponent(code.trim())}`,
        PARENT_HEADERS,
      );
    },

    listSessions() {
      return request<SessionSummary[]>("GET", "/v1/sessions", TEACHER_HEADERS);
    },

    getClassOverview() {
      return request<ClassOverview>("GET", "/v1/teachers/class", TEACHER_HEADERS);
    },

    getStudentReport(studentId) {
      return request<TeacherStudentView>(
        "GET",
        `/v1/teachers/students/${encodeURIComponent(studentId)}`,
        TEACHER_HEADERS,
      );
    },

    getTranscript(sessionId) {
      return request<SessionTranscript>("GET", sessionPath(sessionId, "transcript"), TEACHER_HEADERS);
    },

    getReport(sessionId) {
      return request<TeachingReport>("GET", sessionPath(sessionId, "report"), TEACHER_HEADERS);
    },
  };
}
