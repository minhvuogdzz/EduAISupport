import type {
  ApiErrorCode,
  ChoiceCommand,
  CommandAck,
  EngineKind,
  HintRequestCommand,
  ResponseCommand,
  SessionState,
  SessionSummary,
  SessionTranscript,
  StreamEvent,
  TeachingReport,
} from "./contract";

/**
 * Everything the screens need from the backend. The UI talks only to this interface, so swapping the
 * in-browser mock for the HTTP client of T08 does not touch any screen.
 *
 * Client code never picks a model, lesson or activity: no method takes such a parameter (CLAUDE.md,
 * design rule 4; blueprint PART 24.2).
 */
export interface SessionApi {
  readonly engine: EngineKind;

  /** POST /v1/sessions: demo session for one student (T08). Temporary until login + scheduler exist. */
  createDemoSession(input: { student_display_name: string }): Promise<{ session_id: string }>;
  /** GET /v1/sessions/{id}/state */
  getState(sessionId: string): Promise<SessionState>;
  /** POST /v1/sessions/{id}/join. Joining an ACTIVE session resumes it. */
  join(sessionId: string): Promise<SessionState>;
  /** POST /v1/sessions/{id}/responses */
  submitResponse(sessionId: string, command: ResponseCommand, idempotencyKey: string): Promise<CommandAck>;
  /** POST /v1/sessions/{id}/hint-requests */
  requestHint(sessionId: string, command: HintRequestCommand, idempotencyKey: string): Promise<CommandAck>;
  /** POST /v1/sessions/{id}/choices */
  choose(sessionId: string, command: ChoiceCommand, idempotencyKey: string): Promise<CommandAck>;
  /** GET /v1/sessions/{id}/stream (SSE). Returns the unsubscribe function. */
  subscribe(sessionId: string, onEvent: (event: StreamEvent) => void): () => void;

  /** Student: this student's own sessions, newest first ("Lịch sử học"): GET /v1/sessions/mine. */
  listMySessions(): Promise<SessionSummary[]>;
  /** Teacher: sessions to review. Not in PART 29 yet; proposal: GET /v1/sessions?class_id=… */
  listSessions(): Promise<SessionSummary[]>;
  /** Teacher: GET /v1/sessions/{id}/transcript (audited). */
  getTranscript(sessionId: string): Promise<SessionTranscript>;
  /**
   * Teacher: GET /v1/sessions/{id}/report, how the tutor scored and decided in a chapter session.
   * Real API only: the in-browser mock has no teaching loop.
   */
  getReport?: (sessionId: string) => Promise<TeachingReport>;

  /** Mock only: wipe the demo data kept in this browser and seed it again. */
  resetDemoData?: () => Promise<void>;
}

/** An error response of the session API (`{ error: { code, message, details } }`). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: ApiErrorCode, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** The client acted on an outdated view: re-read GET /state, then let the student retry. */
  get isStale(): boolean {
    return this.code === "STATE_VERSION_CONFLICT" || this.code === "STALE_ITEM";
  }
}
