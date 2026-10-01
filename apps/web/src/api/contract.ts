/**
 * Session API contract as the web app expects it.
 *
 * Sources: blueprint PART 29 (endpoints, command style, SSE events), PART 10.3 (event envelope),
 * PART 16.2 (lifecycle states), PART 24.2 (SessionContext checks and error codes).
 *
 * Hand-written for T09 because the session API (T08) does not exist yet. Once T08 lands, generate
 * these types from FastAPI's OpenAPI schema and delete what the generated types replace
 * (apps/web/README.md, "Nối API thật"). The enum values must stay equal to
 * services/api/cavat/core/pedagogy.py; contract.test.ts fails when they drift.
 */

// ---------------------------------------------------------------- pedagogy vocabulary (pedagogy.py)

export const MOVES = [
  "PRESENT",
  "PROBE",
  "HINT",
  "COGNITIVE_CONFLICT",
  "NUDGE",
  "REDIRECT",
  "OFFER_CHOICE",
  "ASK_CONFIRM",
  "VERIFY",
  "CONFIRM_ADVANCE",
  "WORKED_GUIDANCE",
  "FULL_EXPLANATION",
  "TEACH_BACK",
  "CLOSE_ITEM",
] as const;
export type Move = (typeof MOVES)[number];

/** Moves that deliver hint content (HINT_MOVES in pedagogy.py). */
export const HINT_MOVES: readonly Move[] = [
  "HINT",
  "COGNITIVE_CONFLICT",
  "WORKED_GUIDANCE",
  "FULL_EXPLANATION",
];

export const HINT_TARGETS = ["TASK", "CONCEPT", "STRATEGY", "STEP", "SELF_CHECK", "FORMAT"] as const;
export type HintTarget = (typeof HINT_TARGETS)[number];

/** Math hint ladder H0–H7 (PART 15.1), sent as the integer level. */
export type HintLevel = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

export const OUTCOMES = [
  "CORRECT",
  "WRONG",
  "PARTIAL",
  "UNPARSEABLE",
  "NEEDS_CONFIRMATION",
  "NEEDS_LLM",
  "NO_RESPONSE",
  "HELP_REQUEST",
  "ANSWER_DEMAND",
] as const;
export type Outcome = (typeof OUTCOMES)[number];

export const ERROR_CLASSES = [
  "CONCEPTUAL",
  "PROCEDURAL",
  "CALCULATION",
  "FORMAT",
  "REASONING",
  "UNKNOWN",
] as const;
export type ErrorClass = (typeof ERROR_CLASSES)[number];

export const ACTIVITY_TYPES = [
  "OPENING",
  "WARMUP_REVIEW",
  "CONCEPT_CHECK",
  "TEACH",
  "GUIDED_PRACTICE",
  "INDEPENDENT_PRACTICE",
  "EXIT_ASSESSMENT",
  "SUMMARY",
] as const;
export type ActivityType = (typeof ACTIVITY_TYPES)[number];

export const ITEM_RESOLUTIONS = ["INDEPENDENT", "SUPPORTED", "WORKED", "UNRESOLVED"] as const;
export type ItemResolution = (typeof ITEM_RESOLUTIONS)[number];

// ---------------------------------------------------------------- session runtime (PART 16, 24, 29)

/** Tier 1 of the session state machine (PART 16.2). */
export const LIFECYCLE_STATES = [
  "SCHEDULED",
  "READY",
  "ACTIVE",
  "PAUSED",
  "INTERRUPTED",
  "WRAPPING_UP",
  "COMPLETED",
  "EXITED",
  "INCOMPLETE",
  "MISSED",
  "CANCELLED",
  "FAILED",
] as const;
export type LifecycleState = (typeof LIFECYCLE_STATES)[number];

/**
 * Commands the current state allows (SessionContext.allowed_commands, PART 24.2). The UI only uses
 * this to shape the screen; the backend rejects anything else with 409 (CLAUDE.md, design rule 4).
 */
export type CommandType = "ANSWER" | "HINT_REQUEST" | "CHOICE";

export type ResponseKind = "ANSWER" | "STEP" | "EXPLANATION" | "MESSAGE";
export type Modality = "TEXT" | "VOICE";
export type ActorType = "student" | "tutor" | "system" | "teacher";

/** Answer types of the lesson package; tells the UI which quick-answer buttons fit the item. */
export type AnswerFormat = "compare" | "order" | "numeric" | "choice" | "boolean" | "open";

/** One line of the conversation the student sees. */
export interface ChatTurn {
  turn_id: string;
  sequence_no: number;
  item_attempt_id: string | null;
  actor: ActorType;
  text: string;
  /** ISO 8601, UTC. */
  occurred_at: string;
  /** Tutor turns only. */
  move: Move | null;
  /** Tutor turns that deliver a hint (the UI shows "Gợi ý mức n", PART 29.3). */
  hint_level: HintLevel | null;
}

export interface ItemOption {
  id: string;
  text: string;
}

export interface CurrentItem {
  item_attempt_id: string;
  item_id: string;
  stem: string;
  answer_format: AnswerFormat;
  /** Choice items only. Never carries which option is correct. */
  options: ItemOption[];
  /** What the tutor waits for: the answer, or an explanation after VERIFY / TEACH_BACK. */
  expecting: "ANSWER" | "EXPLANATION";
  /** 1-based position in the session plan. */
  position: number;
}

/** A micro choice the tutor offered (OFFER_CHOICE); answered with POST /choices (PART 24.3, 29.2). */
export interface MicroChoice {
  choice_id: string;
  label: string;
}

/** GET /v1/sessions/{id}/state: full snapshot, also pushed as the SSE `state` event. */
export interface SessionState {
  session_id: string;
  state_version: number;
  lifecycle_state: LifecycleState;
  lesson: { lesson_id: string; title: string };
  /** Given name only (CLAUDE.md, design rule 8). */
  student_display_name: string;
  persona: { tutor_self: string; student_address: string };
  activity: { activity_id: string; type: ActivityType } | null;
  item: CurrentItem | null;
  pending_choice: MicroChoice[] | null;
  allowed_commands: CommandType[];
  progress: { items_done: number; items_total: number };
  /**
   * Turns the student may see. PART 29 asks for at least the current item's turns; the mock sends the
   * whole session. The UI handles both.
   */
  transcript: ChatTurn[];
}

/** Response to every state-changing command (PART 29.3). */
export interface CommandAck {
  accepted: true;
  state_version: number;
  tutor_turn_id: string | null;
}

/**
 * Every state-changing command carries `expected_state_version` in the body and an `Idempotency-Key`
 * header (PART 29.1). PART 29.2 only shows the version on /responses; the web app sends it on
 * /hint-requests and /choices too.
 */
export interface ResponseCommand {
  item_attempt_id: string;
  kind: ResponseKind;
  content: { text: string };
  modality: Modality;
  expected_state_version: number;
}

export interface HintRequestCommand {
  item_attempt_id: string;
  expected_state_version: number;
}

export interface ChoiceCommand {
  choice_id: string;
  expected_state_version: number;
}

/** Events on GET /v1/sessions/{id}/stream (SSE, PART 29.3). Heartbeats stay inside the transport. */
export type StreamEvent =
  | { event: "tutor.delta"; data: { turn_id: string; delta: string } }
  | { event: "tutor.final"; data: ChatTurn }
  | { event: "state"; data: SessionState };

// ---------------------------------------------------------------- teacher views

export type EngineKind = "mock" | "live";

export interface SessionSummary {
  session_id: string;
  student_display_name: string;
  lesson_title: string;
  lifecycle_state: LifecycleState;
  started_at: string | null;
  updated_at: string;
  progress: { items_done: number; items_total: number };
  misconception_ids: string[];
  /** "mock" when the data comes from the in-browser mock, so nobody mistakes it for a real session. */
  engine: EngineKind;
}

export interface TutorAnnotation {
  move: Move;
  hint_level: HintLevel | null;
  hint_target: HintTarget | null;
  rule_ids: string[];
  reason_codes: string[];
}

export interface StudentAnnotation {
  kind: ResponseKind | "HINT_REQUEST" | "CHOICE";
  /** null when the answer was not graded (for example an EXIT item in the mock). */
  outcome: Outcome | null;
  /** Checker's reading of the answer, already formatted vi-VN (e.g. "0,25 > 0,3"). */
  normalized_answer: string | null;
  misconception: { id: string; name: string; confidence: number } | null;
}

export interface TranscriptTurn {
  sequence_no: number;
  occurred_at: string;
  actor: ActorType;
  text: string;
  tutor: TutorAnnotation | null;
  student: StudentAnnotation | null;
}

export interface TranscriptItem {
  item_attempt_id: string;
  item_id: string;
  activity_type: ActivityType;
  stem: string;
  position: number;
  /** null while the item is open, or when it was closed without grading. */
  resolution: ItemResolution | null;
  max_hint_level: HintLevel;
  turns: TranscriptTurn[];
}

/** Turns outside any item (greeting, activity intros, summary) keep their place in the timeline. */
export type TranscriptSegment =
  { kind: "session"; turns: TranscriptTurn[] } | ({ kind: "item" } & TranscriptItem);

/** GET /v1/sessions/{id}/transcript (teacher only, every read is audited: PART 29.2, 30.5). */
export interface SessionTranscript {
  session: SessionSummary;
  segments: TranscriptSegment[];
}

// ---------------------------------------------------------------- errors (PART 24.2, 29.1)

export const API_ERROR_CODES = [
  "NOT_FOUND",
  "VALIDATION_ERROR",
  "NOT_SESSION_OWNER",
  "OUTSIDE_SESSION_WINDOW",
  "INVALID_STATE",
  "COMMAND_NOT_ALLOWED_IN_ACTIVITY",
  "STALE_ITEM",
  "STATE_VERSION_CONFLICT",
] as const;
export type ApiErrorCode = (typeof API_ERROR_CODES)[number];

/** Error body shared by every endpoint: `{ "error": { "code", "message", "details" } }`. */
export interface ApiErrorBody {
  error: { code: ApiErrorCode; message: string; details?: Record<string, unknown> };
}
