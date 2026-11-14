/**
 * A small English tutor session for the in-browser mock (ENG-7a): two nodes of Unit 11 walked through the
 * six steps of ADR-059, so the shared session screen (question card, conversation, answer box, hint button,
 * talk-to-the-teacher button) can be tried for English before the server teaches the unit (ENG-7b).
 *
 * It keeps the server's contract like the math mock does: idempotency keys, `expected_state_version`,
 * the current item, `allowed_commands`, and tutor turns streamed word by word before the new state. It is
 * not the tutor: the checker is a plain normalized comparison (DI-110 in short) and the words are the
 * draft content of ENG-3. Rule ids start with MOCK-.
 */
import { ApiError, type SubjectOverrides } from "../../client";
import type {
  ActivityType,
  ChatTurn,
  CommandAck,
  CurrentItem,
  KnowledgeNode,
  SessionState,
  SessionSummary,
  StreamEvent,
  TeachMessageKind,
} from "../../contract";
import { ME } from "./reports";
import { NODES, RELATIONS, SCRIPT, SESSION_NODES, UNIT, type ScriptStep } from "./unit11";

export interface EnglishSessionOptions {
  storage: Storage | null;
  now: () => Date;
  newId: () => string;
  latencyMs: number;
  typingDelayMs: number;
}

interface EnSession {
  session_id: string;
  version: number;
  lifecycle: "ACTIVE" | "COMPLETED";
  student: string;
  node: number;
  step: number;
  hint: number;
  wrong: number;
  done: number;
  started_at: string;
  updated_at: string;
  transcript: ChatTurn[];
  acks: Record<string, CommandAck>;
}

const KEY = "cavat.mock.english.sessions";
const ACTIVITY: Record<number, ActivityType> = {
  1: "TEACH",
  2: "CONCEPT_CHECK",
  4: "GUIDED_PRACTICE",
  5: "INDEPENDENT_PRACTICE",
};
const ITEMS_TOTAL = SESSION_NODES.reduce(
  (n, id) => n + SCRIPT[id].filter((s) => s.kind === "ITEM").length,
  0,
);
const nodeName = (id: string) => NODES.find((n) => n.node_id === id)?.name ?? id;

/** DI-110 in short: lower case, the punctuation and the extra spaces gone, short forms written out. */
export function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/[’‘]/g, "'")
    .replace(/didn't/g, "did not")
    .replace(/[.,!?;:"“”()–-]/g, " ")
    .replace(/'/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function createEnglishSessions(options: EnglishSessionOptions): SubjectOverrides {
  const { storage, now, newId, latencyMs, typingDelayMs } = options;
  let memory: Record<string, EnSession> = {};
  const listeners = new Map<string, Set<(event: StreamEvent) => void>>();

  function read(): Record<string, EnSession> {
    if (!storage) return memory;
    try {
      return JSON.parse(storage.getItem(KEY) ?? "{}") as Record<string, EnSession>;
    } catch {
      return {};
    }
  }
  function write(db: Record<string, EnSession>) {
    memory = db;
    try {
      storage?.setItem(KEY, JSON.stringify(db));
    } catch {
      // storage full or blocked: the session lives in memory until the page reloads
    }
  }
  function get(db: Record<string, EnSession>, id: string): EnSession {
    const s = db[id];
    if (!s) throw new ApiError(404, "NOT_FOUND", `session ${id} not found`);
    return s;
  }

  function current(s: EnSession): ScriptStep | null {
    const nodeId = SESSION_NODES[s.node];
    return nodeId ? (SCRIPT[nodeId][s.step] ?? null) : null;
  }

  function say(
    s: EnSession,
    text: string,
    kind: TeachMessageKind | null,
    extra: Partial<ChatTurn> = {},
  ): string {
    const turn: ChatTurn = {
      turn_id: newId(),
      sequence_no: s.transcript.length + 1,
      item_attempt_id: null,
      actor: "tutor",
      text,
      occurred_at: now().toISOString(),
      move: null,
      hint_level: null,
      kind,
      node_id: SESSION_NODES[s.node] ?? null,
      ...extra,
    };
    s.transcript.push(turn);
    return turn.turn_id;
  }

  function attemptId(s: EnSession): string {
    return `${s.session_id}:${s.node}:${s.step}`;
  }

  /** Says the current step: an EXAMPLE is told and passed at once; a node ends with step 6. */
  function open(s: EnSession, said: string[]) {
    for (;;) {
      const nodeId = SESSION_NODES[s.node];
      if (!nodeId) {
        said.push(
          say(s, "Hôm nay con ôn được nhiều lắm! Lần sau mình học tiếp phần trọng âm nhé.", "SUMMARY"),
        );
        s.lifecycle = "COMPLETED";
        return;
      }
      const step = SCRIPT[nodeId][s.step];
      if (!step) {
        said.push(say(s, `Con đã qua phần “${nodeName(nodeId)}”. Giỏi quá!`, "PASS"));
        s.node += 1;
        s.step = 0;
        const next = SESSION_NODES[s.node];
        if (next) said.push(say(s, `Bây giờ cô và con cùng ôn: ${nodeName(next)}.`, "NODE"));
        continue;
      }
      s.hint = 0;
      s.wrong = 0;
      if (step.kind === "EXAMPLE") {
        said.push(say(s, step.text, "EXAMPLE"));
        s.step += 1;
        continue;
      }
      if (step.kind === "THEORY") {
        said.push(say(s, `${step.text} ${step.ask}`, "THEORY"));
        return;
      }
      said.push(say(s, step.stem, null, { move: "PRESENT", item_attempt_id: attemptId(s) }));
      return;
    }
  }

  function state(s: EnSession): SessionState {
    const step = current(s);
    const item: CurrentItem | null =
      s.lifecycle === "ACTIVE" && step?.kind === "ITEM"
        ? {
            item_attempt_id: attemptId(s),
            item_id: step.item_id,
            stem: step.stem,
            answer_format: step.format,
            options: step.options ?? [],
            expecting: "ANSWER",
            position: s.done + 1,
          }
        : null;
    const nodeId = SESSION_NODES[s.node] ?? null;
    const passedHere = new Set(SESSION_NODES.slice(0, s.node));
    const nodes: KnowledgeNode[] = NODES.map((n) => {
      const demo = ME.nodes[n.node_id];
      const passed = demo.passed || passedHere.has(n.node_id as (typeof SESSION_NODES)[number]);
      const status = passed
        ? "PASSED"
        : n.node_id === nodeId
          ? "CURRENT"
          : demo.status === "CURRENT"
            ? "AVAILABLE"
            : demo.status;
      return {
        node_id: n.node_id,
        name: n.name,
        layer: n.layer,
        status,
        level: demo.m === null ? null : Math.min(4, Math.floor(demo.m / 20)),
        order: n.order,
      };
    });
    const passed = nodes.filter((n) => n.status === "PASSED").length;
    const theory = s.lifecycle === "ACTIVE" && step?.kind === "THEORY";
    return {
      session_id: s.session_id,
      state_version: s.version,
      lifecycle_state: s.lifecycle,
      lesson: { lesson_id: UNIT.chapter_id, title: UNIT.title },
      student_display_name: s.student,
      persona: { tutor_self: "cô", student_address: "con" },
      activity:
        step && s.lifecycle === "ACTIVE"
          ? { activity_id: `${nodeId}:${step.step}`, type: ACTIVITY[step.step] ?? "TEACH" }
          : null,
      item,
      pending_choice: null,
      allowed_commands: s.lifecycle !== "ACTIVE" ? [] : item ? ["ANSWER", "HINT_REQUEST"] : ["ANSWER"],
      progress: { items_done: s.done, items_total: ITEMS_TOTAL },
      subject: "english",
      teaching: {
        chapter: { ...UNIT },
        current_node_id: s.lifecycle === "ACTIVE" ? nodeId : null,
        step: s.lifecycle === "ACTIVE" ? (step?.step ?? 6) : null,
        awaiting: theory ? "THEORY_REPLY" : item ? "ANSWER" : "NOTHING",
        input_id: theory ? `${attemptId(s)}:reply` : (item?.item_attempt_id ?? null),
        prompt: theory && step?.kind === "THEORY" ? step.ask : null,
        nodes,
        relations: RELATIONS,
        passed,
        total: NODES.length,
      },
      transcript: s.transcript,
    };
  }

  function summary(s: EnSession): SessionSummary {
    return {
      session_id: s.session_id,
      student_display_name: s.student,
      lesson_title: UNIT.title,
      lifecycle_state: s.lifecycle,
      started_at: s.started_at,
      updated_at: s.updated_at,
      progress: { items_done: s.done, items_total: ITEMS_TOTAL },
      misconception_ids: [],
      engine: "mock",
      mode: "CHAPTER",
      subject: "english",
    };
  }

  function publish(id: string, event: StreamEvent) {
    for (const listener of listeners.get(id) ?? []) listener(event);
  }

  async function stream(next: SessionState, turnIds: string[]) {
    for (const turnId of turnIds) {
      const turn = next.transcript.find((t) => t.turn_id === turnId);
      if (!turn) continue;
      for (const word of turn.text.match(/\S+\s*/g) ?? []) {
        await sleep(typingDelayMs);
        publish(next.session_id, { event: "tutor.delta", data: { turn_id: turnId, delta: word } });
      }
      publish(next.session_id, { event: "tutor.final", data: turn });
    }
    publish(next.session_id, { event: "state", data: next });
  }

  function hintOrModel(s: EnSession, step: Extract<ScriptStep, { kind: "ITEM" }>, said: string[]) {
    s.hint += 1;
    const hint = step.hints[s.hint - 1];
    if (hint) {
      said.push(
        say(s, hint, null, {
          move: "HINT",
          hint_level: Math.min(s.hint, 5) as ChatTurn["hint_level"],
          item_attempt_id: attemptId(s),
        }),
      );
      return;
    }
    // H7 (DI-108): the tutor reads the model sentence; the item ends as WORKED and the session goes on.
    said.push(
      say(s, `Cô đọc mẫu nhé: ${step.model} Lần sau con thử tự nói nhé, mình sang câu tiếp.`, null, {
        move: "FULL_EXPLANATION",
        hint_level: 7,
        item_attempt_id: attemptId(s),
      }),
    );
    s.done += 1;
    s.step += 1;
    open(s, said);
  }

  async function command(
    sessionId: string,
    key: string,
    expected: number,
    inputId: string | null,
    kind: "ANSWER" | "HINT_REQUEST",
    apply: (s: EnSession, said: string[]) => void,
  ): Promise<CommandAck> {
    await sleep(latencyMs);
    const db = read();
    const s = get(db, sessionId);
    const replay = s.acks[key];
    if (replay) return replay;
    if (s.lifecycle !== "ACTIVE") throw new ApiError(409, "INVALID_STATE", `session is ${s.lifecycle}`);
    const view = state(s);
    if (inputId !== null && inputId !== view.teaching?.input_id) {
      throw new ApiError(409, "STALE_ITEM", "the item is no longer the current one");
    }
    if (expected !== s.version) {
      throw new ApiError(409, "STATE_VERSION_CONFLICT", "the session changed since the client read it", {
        state_version: s.version,
      });
    }
    if (!view.allowed_commands.includes(kind)) {
      throw new ApiError(409, "COMMAND_NOT_ALLOWED_IN_ACTIVITY", `${kind} is not allowed now`);
    }
    const said: string[] = [];
    apply(s, said);
    s.version += 1;
    s.updated_at = now().toISOString();
    const ack: CommandAck = { accepted: true, state_version: s.version, tutor_turn_id: said[0] ?? null };
    s.acks[key] = ack;
    db[sessionId] = s;
    write(db);
    void stream(state(s), said);
    return ack;
  }

  return {
    async createDemoSession({ student_display_name }) {
      const name = student_display_name.trim();
      if (!name || name.length > 30)
        throw new ApiError(400, "VALIDATION_ERROR", "student_display_name must be 1–30 characters");
      await sleep(latencyMs);
      const at = now().toISOString();
      const s: EnSession = {
        session_id: `eng-${newId()}`,
        version: 1,
        lifecycle: "ACTIVE",
        student: name,
        node: 0,
        step: 0,
        hint: 0,
        wrong: 0,
        done: 0,
        started_at: at,
        updated_at: at,
        transcript: [],
        acks: {},
      };
      say(
        s,
        `Hello ${name}! Hôm nay cô và con ôn ${UNIT.title}. Mình bắt đầu với: ${nodeName(SESSION_NODES[0])}.`,
        "NODE",
      );
      open(s, []);
      const db = read();
      db[s.session_id] = s;
      write(db);
      return { session_id: s.session_id };
    },

    async getState(sessionId) {
      await sleep(latencyMs);
      return state(get(read(), sessionId));
    },

    async join(sessionId) {
      await sleep(latencyMs);
      return state(get(read(), sessionId)); // rejoin = resume (PART 24.4)
    },

    submitResponse(sessionId, cmd, key) {
      if (cmd.content.text.length > 500) {
        return Promise.reject(new ApiError(400, "VALIDATION_ERROR", "text is longer than 500"));
      }
      return command(sessionId, key, cmd.expected_state_version, cmd.item_attempt_id, "ANSWER", (s, said) => {
        s.transcript.push({
          turn_id: newId(),
          sequence_no: s.transcript.length + 1,
          item_attempt_id: cmd.item_attempt_id,
          actor: "student",
          text: cmd.content.text,
          occurred_at: now().toISOString(),
          move: null,
          hint_level: null,
          kind: null,
          node_id: SESSION_NODES[s.node] ?? null,
        });
        const step = current(s);
        const answer = normalize(cmd.content.text);
        if (step?.kind === "THEORY") {
          const ok = step.accept.some((a) => answer.includes(normalize(a)));
          said.push(
            say(s, ok ? step.reply : `Cô cảm ơn con. ${step.reply.replace(/^[^!]*! /, "")}`, "FEEDBACK"),
          );
          s.step += 1;
          open(s, said);
          return;
        }
        if (step?.kind !== "ITEM") return;
        const options = step.options ?? [];
        const picked = options.find((o) => normalize(o.text) === answer || o.id.toLowerCase() === answer);
        const ok = step.accept.some(
          (a) => normalize(a) === answer || normalize(a) === normalize(picked?.id ?? ""),
        );
        if (ok) {
          said.push(
            say(
              s,
              s.hint > 0
                ? "Đúng rồi! Con đã làm được nhờ gợi ý, giỏi lắm."
                : "Đúng rồi! Con tự làm được, giỏi quá!",
              "FEEDBACK",
              {
                move: "CONFIRM_ADVANCE",
              },
            ),
          );
          s.done += 1;
          s.step += 1;
          open(s, said);
          return;
        }
        s.wrong += 1;
        hintOrModel(s, step, said);
      });
    },

    requestHint(sessionId, cmd, key) {
      return command(
        sessionId,
        key,
        cmd.expected_state_version,
        cmd.item_attempt_id,
        "HINT_REQUEST",
        (s, said) => {
          const step = current(s);
          if (step?.kind === "ITEM") hintOrModel(s, step, said);
        },
      );
    },

    choose() {
      return Promise.reject(new ApiError(409, "COMMAND_NOT_ALLOWED_IN_ACTIVITY", "no choice is open"));
    },

    subscribe(sessionId, onEvent) {
      const set = listeners.get(sessionId) ?? new Set();
      set.add(onEvent);
      listeners.set(sessionId, set);
      return () => {
        set.delete(onEvent);
      };
    },

    async listMySessions() {
      await sleep(latencyMs);
      return Object.values(read())
        .map(summary)
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    },

    async listSessions() {
      await sleep(latencyMs);
      return Object.values(read()).map(summary);
    },
  };
}
