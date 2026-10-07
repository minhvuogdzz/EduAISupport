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
  "CLARIFY_REQUEST",
  "OFF_TOPIC",
  "NEGATIVE_AFFECT",
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

/** Messages of the teaching loop (chapter sessions); item messages have no kind. */
export const TEACH_MESSAGE_KINDS = [
  "NODE",
  "THEORY",
  "EXAMPLE",
  "RETELL_PROMPT",
  "FEEDBACK",
  "ANSWER",
  "PASS",
  "STOP",
  "SUMMARY",
] as const;
export type TeachMessageKind = (typeof TEACH_MESSAGE_KINDS)[number];

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
  /** Chapter sessions: what the teaching loop said (theory, worked example, retell prompt...). */
  kind?: TeachMessageKind | null;
  node_id?: string | null;
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
  /** Chapter sessions only (M1-7): the node map and the step of the teaching cycle. */
  teaching?: TeachingView | null;
  /**
   * Turns the student may see. PART 29 asks for at least the current item's turns; the mock sends the
   * whole session. The UI handles both.
   */
  transcript: ChatTurn[];
}

// ---------------------------------------------------------------- teaching on the knowledge graph (M1-7)

export type NodeLayer = "BASIC" | "IMPLEMENT";
export type NodeStatus = "PASSED" | "CURRENT" | "ON_HOLD" | "STOPPED" | "AVAILABLE" | "LOCKED";
export type RelationType = "PREREQUISITE" | "SUBCLASS" | "SIMILAR" | "APPLICATION";
/** What the tutor waits for: an item answer, the reply to a theory question, a retell, or nothing. */
export type TeachingAwaiting = "ANSWER" | "THEORY_REPLY" | "RETELL" | "NOTHING";

export interface KnowledgeNode {
  node_id: string;
  name: string;
  layer: NodeLayer;
  status: NodeStatus;
  /** 0–5 (blueprint §4–§8) once the node has evidence; the student sees words, never the score. */
  level: number | null;
  /** Place in the learning order. */
  order: number;
}

export interface KnowledgeRelation {
  source: string;
  target: string;
  type: RelationType;
}

export interface TeachingView {
  chapter: { chapter_id: string; title: string };
  current_node_id: string | null;
  /** 1–7: step of the teaching cycle (plan v1, 5.2). */
  step: number | null;
  awaiting: TeachingAwaiting;
  /** Sent back as `item_attempt_id` with the student's reply. */
  input_id: string | null;
  /** The question being answered when awaiting THEORY_REPLY or RETELL. */
  prompt: string | null;
  nodes: KnowledgeNode[];
  relations: KnowledgeRelation[];
  passed: number;
  total: number;
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
  /** CHAPTER sessions have a teaching report (GET /v1/sessions/{id}/report). Absent: LESSON. */
  mode?: "LESSON" | "CHAPTER";
}

/** Who worded a tutor message. The move itself always comes from the policy. */
export type MessageSource = "TEMPLATE" | "GENERIC" | "LLM" | "FALLBACK";

export interface TutorAnnotation {
  move: Move;
  hint_level: HintLevel | null;
  hint_target: HintTarget | null;
  rule_ids: string[];
  reason_codes: string[];
  /** Real API only: approved template, generic hint, LLM wording (validated), or fallback sentence. */
  source?: MessageSource;
}

export interface StudentAnnotation {
  kind: ResponseKind | "HINT_REQUEST" | "CHOICE";
  /** null when the answer was not graded (for example an EXIT item in the mock). */
  outcome: Outcome | null;
  /** Checker's reading of the answer, already formatted vi-VN (e.g. "0,25 > 0,3"). */
  normalized_answer: string | null;
  misconception: { id: string; name: string; confidence: number } | null;
  /** A retell judged against the node's key ideas (chapter sessions). */
  retell?: { score: number; ideas_found: number; ideas_total: number } | null;
  /** The child's words raised a safety flag (SAFE-1): the teacher should read them. */
  safety?: boolean;
}

/** The node decision behind a teaching-loop message (chapter sessions). */
export interface TeachAnnotation {
  kind: TeachMessageKind;
  node_id: string | null;
  rule_ids: string[];
  reason_codes: string[];
  /** RAG-2: TEMPLATE: approved text; LLM: Qwen, checked against its sources; EXTRACT: a passage word for word. */
  source?: "TEMPLATE" | "LLM" | "EXTRACT";
  /** Titles of the passages the words rest on. */
  sources?: string[];
  /** Check codes of each model output that was refused. */
  rejected?: string[][];
  /** A question of the child: did the retrieved passages ground it, and why. */
  grounded?: boolean | null;
  grounding?: string | null;
  /** The question was not answered but kept for the teacher. */
  parked?: "NOT_GROUNDED" | "SAME_AS_CHECK" | "LIMIT" | "LATER" | null;
}

export interface TranscriptTurn {
  sequence_no: number;
  occurred_at: string;
  actor: ActorType;
  text: string;
  tutor: TutorAnnotation | null;
  student: StudentAnnotation | null;
  teach?: TeachAnnotation | null;
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

/** Decisions of the node teaching policy (TeachAction in pedagogy.py). */
export const TEACH_ACTIONS = [
  "ENTER_NODE",
  "WARMUP_ITEM",
  "SWITCH_TO_PREREQUISITE",
  "TEACH_THEORY",
  "CHECK_ITEM",
  "ASK_RETELL",
  "SHOW_WORKED_EXAMPLE",
  "COMPLETION_ITEM",
  "PRACTICE_ITEM",
  "TRANSFER_ITEM",
  "REVIEW_ITEM",
  "PASS_NODE",
  "STOP_NODE",
  "FINISH",
] as const;
export type TeachAction = (typeof TEACH_ACTIONS)[number];

/** The seven dimensions of the math framework (blueprint PART 26.1). */
export const DIMENSIONS = ["C", "R", "A", "T", "I", "S", "D"] as const;
export type Dimension = (typeof DIMENSIONS)[number];

export interface ReportNode {
  node_id: string;
  name: string;
  layer: NodeLayer;
  status: NodeStatus;
  prior: number;
  /** M on 0–100; null until a dimension has enough evidence. */
  mastery: number | null;
  confidence: number;
  level: number;
  state: string;
  insufficient_data: boolean;
  dimensions: Record<Dimension, { mean: number; n_eff: number; in_mastery: boolean }>;
  items: number;
  successes: number;
  levels: string[];
  forms: string[];
  understood: boolean;
  has_explanation: boolean;
  has_application: boolean;
  misconceptions: { id: string; name: string; severity: string; count: number; status: string }[];
  pass_now: boolean;
  passed: boolean;
  /** MASTERY, UNDERSTOOD, EXPLANATION, APPLICATION, MISCONCEPTION. */
  missing: string[];
  pass_rule: {
    min_mastery: number;
    min_successes: number;
    min_levels: number;
    min_forms: number;
    max_items: number;
  };
}

export interface EvidenceEntry {
  sequence_no: number;
  occurred_at: string;
  /** From an earlier session of the student: the tutor remembers it. */
  earlier?: boolean;
  node_id: string;
  dimension: Dimension;
  /** 1 counts fully for the node, 0 against it. */
  score: number;
  weight: number;
  reason: string;
  item_id: string | null;
}

export interface MasteryPoint {
  sequence_no: number;
  occurred_at: string;
  earlier?: boolean;
  node_id: string;
  mastery: number | null;
}

export interface DecisionEntry {
  sequence_no: number;
  occurred_at: string;
  action: TeachAction;
  node_id: string | null;
  ref: string | null;
  support: string | null;
  rule_ids: string[];
  reason_codes: string[];
}

/** GET /v1/sessions/{id}/report (teacher): how the tutor scored and decided, replayed from the events. */
export interface TeachingReport {
  session: SessionSummary;
  chapter: { chapter_id: string; title: string; version: string };
  versions: Record<string, string>;
  current_node_id: string | null;
  /** Sessions of the student on this chapter before this one; their evidence counts. */
  earlier_sessions?: number;
  nodes: ReportNode[];
  relations: KnowledgeRelation[];
  evidence: EvidenceEntry[];
  trace: MasteryPoint[];
  decisions: DecisionEntry[];
}

// ---------------------------------------------------------------- student and parent views (PART 27.1)

/** DI-14: understanding of a topic in words, shared by students and parents (no score shown). */
export type Quality =
  "NOT_STARTED" | "INSUFFICIENT_DATA" | "FAMILIAR" | "WITH_SUPPORT" | "INDEPENDENT" | "SOLID";

export interface ProgressNode {
  node_id: string;
  name: string;
  layer: NodeLayer;
  status: NodeStatus;
  level: number | null;
  quality: Quality;
  order: number;
  passed: boolean;
}

export interface ProgressTopic {
  node_id: string;
  name: string;
  quality: Quality;
  reason?: string | null;
}

/** GET /v1/students/me/overview: the chapter so far, across the student's sessions. */
export interface StudentOverview {
  student_display_name: string;
  /** The code the parent enters to follow this child (demo guardian link). */
  parent_code: string;
  chapter: { chapter_id: string; title: string };
  nodes: ProgressNode[];
  relations: KnowledgeRelation[];
  passed: number;
  total: number;
  sessions: { total: number; completed: number; unfinished: number; minutes: number };
  /** Local dates (YYYY-MM-DD) with learning. */
  study_days: string[];
  streak: number;
  this_week: { study_days: number; passed: number };
  going_well: ProgressTopic[];
  to_practise: ProgressTopic[];
  current_session_id: string | null;
  last_session_at: string | null;
}

/** GET /v1/parents/children/{code}: the student's overview, four weeks of trend, help at home. */
export interface ParentChildView extends StudentOverview {
  trend: { date: string; studied: boolean; passed: number; started: number }[];
  home_tips: { node_id: string; name: string; tip: string }[];
  session_list: {
    session_id: string;
    started_at: string;
    minutes: number;
    lifecycle_state: LifecycleState;
    passed_names: string[];
  }[];
}

// ---------------------------------------------------------------- the teacher's class view (PART 27.1, §56)

export interface TeacherNode {
  node_id: string;
  name: string;
  layer: NodeLayer;
  order: number;
  /** The pass threshold of M for this node (DI-15). */
  min_mastery: number;
}

/** One student on one KC (§46): M on 0-100, confidence (DI-7: below 30 shown with a warning). */
export interface MasteryCell {
  node_id: string;
  mastery: number | null;
  confidence: number;
  level: number;
  state: string;
  insufficient_data: boolean;
  passed: boolean;
  status: NodeStatus;
  active_misconceptions: number;
}

/** Why the teacher should look at a student (PART 27.1, DI-20). SAFETY comes first (SAFE-1). */
export interface AttentionReason {
  kind: "SAFETY" | "STOPPED" | "MISCONCEPTION" | "WEAK" | "INACTIVE";
  node_id?: string | null;
  misconception_id?: string | null;
  count?: number | null;
  mastery?: number | null;
  days?: number | null;
  /** SAFETY: the session where the child said something worrying, and when. */
  session_id?: string | null;
  at?: string | null;
}

/** §23: overall mastery of the KCs with a score, and the share of KCs that have one (DI-21). */
export interface OverallMastery {
  mastery: number | null;
  confidence: number | null;
  level: number | null;
  coverage: number;
}

export interface ClassStudent {
  student_id: string;
  display_name: string;
  sessions: { total: number; completed: number; unfinished: number; minutes: number };
  last_active_at: string | null;
  passed: number;
  overall: OverallMastery;
  cells: MasteryCell[];
  attention: AttentionReason[];
}

/** §28: one misconception in the class. `share` is its percentage of all detections. */
export interface ClassMisconception {
  id: string;
  name: string;
  node_id: string | null;
  severity: string;
  count: number;
  share: number;
  students: number;
  active_students: number;
  /** Detections in the last 14 days (§28). */
  recent: number;
}

/** GET /v1/teachers/class. */
export interface ClassOverview {
  chapter: { chapter_id: string; title: string };
  nodes: TeacherNode[];
  students: ClassStudent[];
  /** §45: the class on each KC, over the students with a score. */
  by_node: { node_id: string; mean_mastery: number | null; students: number; passed: number }[];
  misconceptions: ClassMisconception[];
  kpis: {
    students: number;
    active_this_week: number;
    sessions: number;
    minutes: number;
    passed: number;
    cells: number;
    mean_mastery: number | null;
    attention: number;
  };
}

export type KcGroup = "PASSED" | "UNSTABLE" | "WEAK" | "INSUFFICIENT" | "NOT_STARTED";
export type Recommendation = "DIAGNOSE" | "EXPLAIN" | "GUIDED" | "PRACTICE" | "TRANSFER" | "CHALLENGE";

/** §57: one KC of one student. */
export interface TeacherNodeDetail extends TeacherNode, Omit<MasteryCell, "node_id"> {
  group: KcGroup;
  dimensions: Record<Dimension, { value: number; n_eff: number; in_mastery: boolean }>;
  items: number;
  solved: number;
  attempts: number;
  hints: number;
  /** Average seconds per item. */
  seconds: number | null;
  misconceptions: { id: string; name: string; severity: string; count: number; status: string }[];
  trend: { at: string; mastery: number }[];
  direction: "UP" | "FLAT" | "DOWN" | null;
  recommendation: Recommendation;
}

/** GET /v1/teachers/students/{id}. */
export interface TeacherStudentView {
  student_id: string;
  display_name: string;
  chapter: { chapter_id: string; title: string };
  relations: KnowledgeRelation[];
  sessions: { total: number; completed: number; unfinished: number; minutes: number };
  session_list: ParentChildView["session_list"];
  last_active_at: string | null;
  overall: OverallMastery & { passed: number; total: number };
  /** Each dimension over the chapter on 0-100 (DI-22); null: not enough evidence. */
  dimensions: Record<Dimension, { value: number | null; n_eff: number }>;
  strengths: Dimension[];
  weaknesses: Dimension[];
  nodes: TeacherNodeDetail[];
  /** §27: overall M at the end of each day with evidence (DI-26). */
  timeline: { date: string; mastery: number }[];
  /** §39: change of overall M since before this week (DI-25). */
  velocity: { change: number; since: string } | null;
  /** §56: per day, how the items ended, hints and KCs passed. */
  activity: {
    date: string;
    independent: number;
    supported: number;
    worked: number;
    unresolved: number;
    hints: number;
    passed: number;
  }[];
  attention: AttentionReason[];
}

// ---------------------------------------------------------------- accounts (ACC-1)

export type AccountKind = "STUDENT" | "PARENT" | "TEACHER";

/** GET /v1/auth/config: the three trial accounts, or the demo mode (no login). */
export interface AuthConfig {
  mode: "accounts" | "demo";
  accounts: { kind: AccountKind; login_name: string; display_name: string }[];
}

/** The logged-in account (POST /v1/auth/login, GET /v1/auth/me). */
export interface AuthUser {
  user_id: string;
  kind: AccountKind;
  display_name: string;
  child_id: string | null;
}

// ---------------------------------------------------------------- teacher library and lesson content (DOC-1)

export type DocumentKind = "SGK" | "GIAO_AN" | "BAI_TAP" | "DE_KIEM_TRA" | "KHAC";

/** A document the teacher uploaded; its text feeds the Hybrid RAG. */
export interface TeacherDocument {
  document_id: string;
  title: string;
  kind: DocumentKind;
  chapter_id: string | null;
  filename: string;
  content_type: string;
  size: number;
  uploaded_at: string;
  /** READ: text read; NEEDS_OCR: a scan or photo with no OCR configured; FAILED: unreadable. */
  status: "READ" | "NEEDS_OCR" | "FAILED";
  method: string;
  pages: number;
  chars: number;
  error: string | null;
}

export interface TeacherDocumentDetail extends TeacherDocument {
  text: string;
}

export interface ChapterSummary {
  chapter_id: string;
  title: string;
  status: string;
  nodes: number;
  items: number;
}

export interface ContentItem {
  item_id: string;
  stage: string;
  purpose: string;
  cognitive_level: string;
  difficulty: number;
  stem: string;
  answer_type: string;
  answer: string;
  hints: { level: number; target: string; text: string }[];
  worked_solution: string[];
  explanation: string | null;
  wrong_answers: Record<string, string>;
}

export interface ContentNode {
  node_id: string;
  name: string;
  layer: NodeLayer;
  description: string;
  home_tip: string;
  theory: {
    id: string;
    representation: string;
    text: string;
    ask: string;
    reply: string;
    accept: string[];
  }[];
  method: { rule: string; steps: string[] };
  worked_examples: { id: string; problem: string; steps: string[]; answer: string }[];
  retell: { prompt: string; key_ideas: string[][] };
  items: ContentItem[];
  pass_rule: { min_mastery: number };
}

/** GET /v1/teachers/chapters/{id}: what the tutor teaches, with the answers (teacher only). */
export interface ChapterContent {
  chapter_id: string;
  title: string;
  version: string;
  status: string;
  source: string;
  nodes: ContentNode[];
  relations: KnowledgeRelation[];
  misconceptions: {
    id: string;
    kc_id: string;
    name: string;
    description: string;
    severity: string;
    counter_examples: string[];
  }[];
}

// ---------------------------------------------------------------- Hybrid RAG, teacher view (RAG-1)

/** GET /v1/teachers/rag/status: where the RAG takes its passages from. */
export interface RagStatus {
  chunks: number;
  /** "chapter" (approved or draft teaching content) and "document" (the teacher's uploads). */
  by_source: Record<string, number>;
  /** theory, method, worked_example, misconception_note, source_passage */
  by_kind: Record<string, number>;
  nodes: { node_id: string; name: string; chunks: number }[];
  documents: { document_id: string; title: string; status: string; passages: number; tied_to_node: number }[];
  /** The embedding model, or "off": keywords and structure only. */
  semantic: string;
  /** False for the offline trigram vectors (tests): spelling, not meaning. */
  semantic_is_model: boolean;
  semantic_error: string | null;
  built_at: string | null;
}

/** question: a child's free question; teach: the next way of teaching a node; hint: material for a hint. */
export type RagMode = "question" | "teach" | "hint";

export interface RagResult {
  chunk_id: string;
  title: string;
  kind: string;
  source: string;
  node_id: string | null;
  node_name: string | null;
  document_id: string | null;
  page: number | null;
  approved: boolean;
  text: string;
  bm25: number;
  bm25_rank: number | null;
  cosine: number;
  cosine_rank: number | null;
  /** Steps from the node asked for on the knowledge graph (0 without a node). */
  distance: number;
  /** Reciprocal Rank Fusion, weighted by 1 / (1 + distance). */
  fused: number;
  /** After the pedagogical re-ranking. */
  final: number;
  /** Share of the question's content words found in the passage. */
  coverage: number;
  reasons: string[];
}

/** GET /v1/teachers/rag/search: the six steps of one retrieval, every signal shown. */
export interface RagSearch {
  query: string;
  node_id: string | null;
  /** "definition" when a free question asks what something is ("… là gì"). */
  mode: RagMode | "definition";
  grounded: boolean;
  grounding: string;
  semantic: string;
  candidates: number;
  elapsed_ms: number;
  results: RagResult[];
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
