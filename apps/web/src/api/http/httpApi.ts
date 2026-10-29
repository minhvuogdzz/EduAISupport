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
import { ApiError, type SessionApi } from "../client";
import {
  API_ERROR_CODES,
  type ApiErrorCode,
  type AccountKind,
  type AuthConfig,
  type AuthUser,
  type TeachingPlanReview,
  type FigureView,
  type TeacherFigure,
  type ChapterContent,
  type ChapterSummary,
  type ChatTurn,
  type ClassOverview,
  type CommandAck,
  type SessionState,
  type SessionSummary,
  type ParentChildView,
  type RagSearch,
  type RagStatus,
  type SafetyReview,
  type SessionTranscript,
  type StreamEvent,
  type StudentOverview,
  type TeacherDocument,
  type TeacherDocumentDetail,
  type TeachingReport,
  type TeacherStudentView,
  type VoiceStatus,
} from "../contract";

export interface HttpApiOptions {
  /** Origin of the API. "" (default) uses the page's origin: the Vite dev server proxies /v1. */
  baseUrl?: string;
  fetch?: typeof fetch;
  /** Where the login token is kept. Default: localStorage when usable. null: memory only. */
  storage?: Storage | null;
  /** Delay between the words of a new tutor turn, in ms. */
  typingDelayMs?: number;
}

/**
 * The one student of the trial when no account logs in (AUTH_MODE=demo, ACC-2): every browser is the same
 * child, as with accounts. A random id per browser made each new browser a new student.
 */
export const DEMO_STUDENT_ID = "demo-student";
export const DEMO_STUDENT_NAME = "An";
/** The kept login of each role on this device (ACC-2), and which role is current. */
const TOKENS_KEY = "cavat.auth.tokens";
const CURRENT_KEY = "cavat.auth.current";
const TEACHER_HEADERS = { "X-Demo-Teacher": "web" };
const PARENT_HEADERS = { "X-Demo-Parent": "web" };

function browserStorage(): Storage | null {
  try {
    return globalThis.localStorage;
  } catch {
    return null; // storage blocked: the identity then lasts until the page is reloaded
  }
}

/** `?chapter=<id>` for the views that name a chapter; nothing when none is named (the first one). */
function chapterQuery(chapterId: string | undefined): string {
  return chapterId ? `?chapter=${encodeURIComponent(chapterId)}` : "";
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
  const storage = options.storage === undefined ? browserStorage() : options.storage;

  const listeners = new Map<string, Set<(event: StreamEvent) => void>>();
  /** Highest sequence_no this client has already shown, per session: newer tutor turns are streamed. */
  const seen = new Map<string, number>();

  // In memory first: storage may be blocked, then the logins last until the page is reloaded.
  let tokens: Partial<Record<AccountKind, string>> = readStored(TOKENS_KEY) ?? {};
  let current: AccountKind | null = readStored(CURRENT_KEY);

  function readStored<T>(key: string): T | null {
    try {
      const raw = storage?.getItem(key);
      return raw ? (JSON.parse(raw) as T) : null;
    } catch {
      return null;
    }
  }

  function store(): void {
    try {
      storage?.setItem(TOKENS_KEY, JSON.stringify(tokens));
      if (current === null) storage?.removeItem(CURRENT_KEY);
      else storage?.setItem(CURRENT_KEY, JSON.stringify(current));
    } catch {
      // storage blocked: kept in memory only
    }
  }

  /** Keeps a login: the asked role is current, and a child's login also keeps the parent's token. */
  function keep(result: { token: string; user: AuthUser; parent_token?: string | null }): AuthUser {
    tokens = { ...tokens, [result.user.kind]: result.token };
    if (result.parent_token) tokens.PARENT = result.parent_token;
    current = result.user.kind;
    store();
    return result.user;
  }

  function token(): string | null {
    return current ? (tokens[current] ?? null) : null;
  }

  /** The logged-in account (ACC-1); the X-Demo-* headers only without a login (AUTH_MODE=demo). */
  function as(demo: () => Record<string, string>): Record<string, string> {
    const current = token();
    return current ? { Authorization: `Bearer ${current}` } : demo();
  }

  function studentHeaders(): Record<string, string> {
    return as(demoStudentHeaders);
  }

  function demoStudentHeaders(): Record<string, string> {
    return { "X-Demo-Student": DEMO_STUDENT_ID };
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

  /** A request whose body or answer is not JSON (an upload, a deletion, a file). */
  async function send(
    method: "GET" | "POST" | "DELETE",
    path: string,
    headers: Record<string, string>,
    body?: FormData,
  ): Promise<Response> {
    const response = await doFetch(`${baseUrl}${path}`, { method, headers, body });
    if (!response.ok) throw await toError(response);
    return response;
  }

  const teacher = () => as(() => TEACHER_HEADERS);
  const planPath = (chapterId: string) => `/v1/teachers/teaching-plans/${encodeURIComponent(chapterId)}`;
  const documentPath = (id: string, tail = "") => `/v1/teachers/documents/${encodeURIComponent(id)}${tail}`;

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

    async createDemoSession({ student_display_name, chapter_id }) {
      // The API calls the chapter to learn `lesson_id`; the server refuses an id it does not teach.
      const body = { student_display_name, lesson_id: chapter_id };
      const state = await request<SessionState>("POST", "/v1/sessions", studentHeaders(), body);
      return { session_id: state.session_id };
    },

    async getState(sessionId) {
      return remember(await request<SessionState>("GET", sessionPath(sessionId, "state"), studentHeaders()));
    },

    async join(sessionId) {
      return remember(await request<SessionState>("POST", sessionPath(sessionId, "join"), studentHeaders()));
    },

    recover(sessionId, version, idempotencyKey) {
      return command(sessionId, "recover", { expected_state_version: version }, idempotencyKey);
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

    getMyOverview(chapterId) {
      return request<StudentOverview>(
        "GET",
        `/v1/students/me/overview${chapterQuery(chapterId)}`,
        studentHeaders(),
      );
    },

    getChildOverview(code, chapterId) {
      return request<ParentChildView>(
        "GET",
        `/v1/parents/children/${encodeURIComponent(code.trim())}${chapterQuery(chapterId)}`,
        as(() => PARENT_HEADERS),
      );
    },

    listSessions() {
      return request<SessionSummary[]>(
        "GET",
        "/v1/sessions",
        as(() => TEACHER_HEADERS),
      );
    },

    auth: {
      config() {
        return request<AuthConfig>("GET", "/v1/auth/config", {});
      },
      async login(loginName, pin, role) {
        const result = await request<{ token: string; user: AuthUser; parent_token?: string | null }>(
          "POST",
          "/v1/auth/login",
          {},
          { login_name: loginName, pin, role },
        );
        return keep(result);
      },
      async register(username, passcode) {
        const result = await request<{ token: string; user: AuthUser; parent_token?: string | null }>(
          "POST",
          "/v1/auth/student/register",
          {},
          { username, passcode },
        );
        return keep(result);
      },
      me() {
        const current = token();
        if (!current) return Promise.reject(new ApiError(401, "NOT_SESSION_OWNER", "please log in"));
        return request<AuthUser>("GET", "/v1/auth/me", { Authorization: `Bearer ${current}` });
      },
      switchTo(kind) {
        if (!tokens[kind]) return false;
        current = kind;
        store();
        return true;
      },
      logout() {
        // A child's account is also the parent's: leaving one leaves both.
        const child = current === "STUDENT" || current === "PARENT";
        if (current) {
          tokens = Object.fromEntries(
            Object.entries(tokens).filter(
              ([kind]) => kind !== current && !(child && (kind === "STUDENT" || kind === "PARENT")),
            ),
          );
        }
        current = null;
        store();
      },
    },

    voice: {
      status() {
        return request<VoiceStatus>("GET", "/v1/voice/status", studentHeaders());
      },
      async transcribe(audio) {
        const form = new FormData();
        const ext = audio.type.includes("ogg") ? "ogg" : audio.type.includes("mp4") ? "m4a" : "webm";
        form.append("audio", audio, `turn.${ext}`);
        const response = await send("POST", "/v1/voice/transcribe", studentHeaders(), form);
        return (await response.json()) as { text: string };
      },
      async speech(text) {
        const response = await doFetch(`${baseUrl}/v1/voice/speech`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...studentHeaders() },
          body: JSON.stringify({ text }),
        });
        if (!response.ok) throw await toError(response);
        return response.blob();
      },
    },
    library: {
      list() {
        return request<TeacherDocument[]>("GET", "/v1/teachers/documents", teacher());
      },
      get(documentId) {
        return request<TeacherDocumentDetail>("GET", documentPath(documentId), teacher());
      },
      async upload(file, meta) {
        const form = new FormData();
        form.append("file", file, file.name);
        form.append("title", meta.title);
        form.append("kind", meta.kind);
        form.append("chapter_id", meta.chapterId);
        const response = await send("POST", "/v1/teachers/documents", teacher(), form);
        return (await response.json()) as TeacherDocument;
      },
      async remove(documentId) {
        await send("DELETE", documentPath(documentId), teacher());
      },
      async original(documentId) {
        return (await send("GET", documentPath(documentId, "/file"), teacher())).blob();
      },
      chapters() {
        return request<ChapterSummary[]>("GET", "/v1/teachers/chapters", teacher());
      },
      chapter(chapterId) {
        return request<ChapterContent>(
          "GET",
          `/v1/teachers/chapters/${encodeURIComponent(chapterId)}`,
          teacher(),
        );
      },
    },

    plans: {
      view(chapterId) {
        return request<TeachingPlanReview>("GET", `${planPath(chapterId)}/view`, teacher());
      },
      build(chapterId) {
        return request<unknown>("POST", `${planPath(chapterId)}/build`, teacher());
      },
      decide(chapterId, target, action, value) {
        return request<unknown>("POST", `${planPath(chapterId)}/decisions`, teacher(), {
          target,
          action,
          value,
        });
      },
      async undo(chapterId, target) {
        const params = new URLSearchParams({ target });
        const response = await send(
          "DELETE",
          `${planPath(chapterId)}/decisions?${params.toString()}`,
          teacher(),
        );
        return (await response.json()) as unknown;
      },
      publish(chapterId) {
        return request<unknown>("POST", `${planPath(chapterId)}/publish`, teacher());
      },
    },

    figures: {
      list(chapterId, who) {
        const headers = who === "teacher" ? teacher() : studentHeaders();
        return request<FigureView[]>(
          "GET",
          `/v1/figures?chapter_id=${encodeURIComponent(chapterId)}`,
          headers,
        );
      },
      async image(figureId, version, who) {
        const headers = who === "teacher" ? teacher() : studentHeaders();
        const path = `/v1/figures/${encodeURIComponent(figureId)}/image?v=${encodeURIComponent(version)}`;
        return (await send("GET", path, headers)).blob();
      },
      all(chapterId) {
        return request<TeacherFigure[]>(
          "GET",
          `/v1/teachers/figures?chapter_id=${encodeURIComponent(chapterId)}`,
          teacher(),
        );
      },
      decide(figureId, action) {
        return request<TeacherFigure>(
          "POST",
          `/v1/teachers/figures/${encodeURIComponent(figureId)}/decision`,
          teacher(),
          { action },
        );
      },
      async replace(file, meta) {
        const form = new FormData();
        form.set("file", file);
        form.set("chapter_id", meta.chapterId);
        form.set("question_id", meta.questionId);
        form.set("order", String(meta.order));
        form.set("tag", meta.tag);
        return (await (await send("POST", "/v1/teachers/figures", teacher(), form)).json()) as TeacherFigure;
      },
    },

    rag: {
      status() {
        return request<RagStatus>("GET", "/v1/teachers/rag/status", teacher());
      },
      rebuild() {
        return request<RagStatus>("POST", "/v1/teachers/rag/rebuild", teacher());
      },
      search(query, { nodeId, mode, k = 5 }) {
        const params = new URLSearchParams({ q: query, mode, k: String(k) });
        if (nodeId) params.set("node", nodeId);
        return request<RagSearch>("GET", `/v1/teachers/rag/search?${params.toString()}`, teacher());
      },
    },

    getMyChild(chapterId) {
      return request<ParentChildView>(
        "GET",
        `/v1/parents/me/child${chapterQuery(chapterId)}`,
        as(() => PARENT_HEADERS),
      );
    },

    getTaughtChapters() {
      return request<{ chapter_id: string; title: string }[]>(
        "GET",
        "/v1/teachers/taught-chapters",
        as(() => TEACHER_HEADERS),
      );
    },

    getClassOverview(chapterId) {
      return request<ClassOverview>(
        "GET",
        `/v1/teachers/class${chapterQuery(chapterId)}`,
        as(() => TEACHER_HEADERS),
      );
    },

    markSafetyReviewed(sessionId) {
      return request<SafetyReview>(
        "POST",
        "/v1/teachers/safety-reviews",
        as(() => TEACHER_HEADERS),
        { session_id: sessionId },
      );
    },

    getStudentReport(studentId, chapterId) {
      return request<TeacherStudentView>(
        "GET",
        `/v1/teachers/students/${encodeURIComponent(studentId)}${chapterQuery(chapterId)}`,
        as(() => TEACHER_HEADERS),
      );
    },

    getTranscript(sessionId) {
      return request<SessionTranscript>(
        "GET",
        sessionPath(sessionId, "transcript"),
        as(() => TEACHER_HEADERS),
      );
    },

    getReport(sessionId) {
      return request<TeachingReport>(
        "GET",
        sessionPath(sessionId, "report"),
        as(() => TEACHER_HEADERS),
      );
    },
  };
}
