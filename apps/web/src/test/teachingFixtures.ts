/** Test data of a chapter session (M1-7): a small graph and the views the API returns for it. */
import type {
  ChatTurn,
  KnowledgeNode,
  KnowledgeRelation,
  ReportNode,
  SessionState,
  TeachingReport,
  TeachingView,
} from "../api/contract";

export const NODES: KnowledgeNode[] = [
  { node_id: "KC-DEC-FRAC", name: "Phân số thập phân", layer: "BASIC", status: "PASSED", level: 4, order: 0 },
  {
    node_id: "KC-DEC-CONCEPT",
    name: "Khái niệm số thập phân",
    layer: "BASIC",
    status: "CURRENT",
    level: 2,
    order: 1,
  },
  {
    node_id: "KC-DEC-CMP",
    name: "So sánh hai số thập phân",
    layer: "IMPLEMENT",
    status: "LOCKED",
    level: null,
    order: 2,
  },
];

export const RELATIONS: KnowledgeRelation[] = [
  { source: "KC-DEC-FRAC", target: "KC-DEC-CONCEPT", type: "PREREQUISITE" },
  { source: "KC-DEC-CONCEPT", target: "KC-DEC-CMP", type: "APPLICATION" },
];

export const THEORY_TEXT =
  "Sợi dây dài 2 m 7 dm, viết gọn là 2,7 m. Trong số đo 2,7 m, phần nào cho biết số mét tròn?";
export const THEORY_ASK = "Trong số đo 2,7 m, phần nào cho biết số mét tròn?";

function turn(
  sequence_no: number,
  kind: ChatTurn["kind"],
  text: string,
  actor: ChatTurn["actor"] = "tutor",
): ChatTurn {
  return {
    turn_id: `t${sequence_no}`,
    sequence_no,
    item_attempt_id: null,
    actor,
    text,
    occurred_at: "2026-10-06T08:00:00Z",
    move: null,
    hint_level: null,
    kind,
    node_id: "KC-DEC-CONCEPT",
  };
}

export function teachingView(overrides: Partial<TeachingView> = {}): TeachingView {
  return {
    chapter: { chapter_id: "math-g5-decimals", title: "Số thập phân" },
    current_node_id: "KC-DEC-CONCEPT",
    step: 2,
    awaiting: "THEORY_REPLY",
    input_id: "in-1",
    prompt: THEORY_ASK,
    nodes: NODES,
    relations: RELATIONS,
    passed: 1,
    total: 3,
    ...overrides,
  };
}

/** Waiting for the student's reply to the question that ends a theory explanation. */
export function theoryState(): SessionState {
  return {
    session_id: "s-1",
    state_version: 3,
    lifecycle_state: "ACTIVE",
    lesson: { lesson_id: "math-g5-decimals", title: "Số thập phân" },
    student_display_name: "An",
    persona: { tutor_self: "cô", student_address: "con" },
    activity: { activity_id: "KC-DEC-CONCEPT:2", type: "TEACH" },
    item: null,
    pending_choice: null,
    allowed_commands: ["ANSWER"],
    progress: { items_done: 1, items_total: 3 },
    transcript: [
      turn(1, "NODE", "Bây giờ cô và con cùng học: Khái niệm số thập phân."),
      turn(2, "THEORY", THEORY_TEXT),
    ],
    teaching: teachingView(),
  };
}

/** The next state: a concept-check item of the current node is open. */
export function checkState(reply: string): SessionState {
  const state = theoryState();
  return {
    ...state,
    state_version: 4,
    activity: { activity_id: "KC-DEC-CONCEPT:3", type: "CONCEPT_CHECK" },
    item: {
      item_attempt_id: "att-1",
      item_id: "KN-CC-01",
      stem: "Số 12,45 có phần nguyên là bao nhiêu?",
      answer_format: "numeric",
      options: [],
      expecting: "ANSWER",
      position: 1,
    },
    allowed_commands: ["ANSWER", "HINT_REQUEST"],
    transcript: [
      ...state.transcript,
      turn(3, null, reply, "student"),
      turn(4, "FEEDBACK", "Cô cảm ơn con."),
      { ...turn(5, null, "Số 12,45 có phần nguyên là bao nhiêu?"), move: "PRESENT" },
    ],
    teaching: teachingView({ step: 3, awaiting: "ANSWER", input_id: "att-1", prompt: null }),
  };
}

function reportNode(overrides: Partial<ReportNode>): ReportNode {
  const dims = { mean: 0.5, n_eff: 0, in_mastery: false };
  return {
    node_id: "KC-DEC-FRAC",
    name: "Phân số thập phân",
    layer: "BASIC",
    status: "PASSED",
    prior: 0.5,
    mastery: 75.3,
    confidence: 41.2,
    level: 4,
    state: "APPLIED",
    insufficient_data: false,
    dimensions: {
      C: { mean: 0.7928, n_eff: 2.825, in_mastery: true },
      R: { mean: 0.6667, n_eff: 1, in_mastery: true },
      A: { mean: 0.661, n_eff: 0.95, in_mastery: false },
      T: dims,
      I: { mean: 0.8462, n_eff: 4.5, in_mastery: true },
      S: dims,
      D: dims,
    },
    items: 5,
    successes: 4,
    levels: ["A", "B", "D"],
    forms: ["choice", "numeric"],
    understood: true,
    has_explanation: true,
    has_application: true,
    misconceptions: [],
    pass_now: true,
    passed: true,
    missing: [],
    pass_rule: { min_mastery: 75, min_successes: 3, min_levels: 2, min_forms: 2, max_items: 12 },
    ...overrides,
  };
}

export function report(): TeachingReport {
  const at = "2026-10-06T08:05:00Z";
  return {
    session: {
      session_id: "s-1",
      student_display_name: "An",
      lesson_title: "Số thập phân",
      lifecycle_state: "ACTIVE",
      started_at: "2026-10-06T08:00:00Z",
      updated_at: at,
      progress: { items_done: 1, items_total: 3 },
      misconception_ids: ["CONCEPT-M02"],
      engine: "live",
      mode: "CHAPTER",
    },
    chapter: { chapter_id: "math-g5-decimals", title: "Số thập phân", version: "0.1.0" },
    versions: {
      mastery: "node-mastery/0.1.0",
      policy: "node-policy/0.1.0",
      templates: "teaching-templates/0.1.0",
    },
    current_node_id: "KC-DEC-CONCEPT",
    nodes: [
      reportNode({}),
      reportNode({
        node_id: "KC-DEC-CONCEPT",
        name: "Khái niệm số thập phân",
        status: "CURRENT",
        mastery: 58.4,
        level: 2,
        state: "PROCEDURAL",
        understood: false,
        has_application: false,
        successes: 1,
        levels: ["A"],
        forms: ["numeric"],
        pass_now: false,
        passed: false,
        missing: ["MASTERY", "UNDERSTOOD", "APPLICATION", "MISCONCEPTION"],
        misconceptions: [
          {
            id: "CONCEPT-M02",
            name: "Bỏ chữ số 0 ngay sau dấu phẩy",
            severity: "CRITICAL",
            count: 1,
            status: "ACTIVE",
          },
        ],
      }),
      reportNode({
        node_id: "KC-DEC-CMP",
        name: "So sánh hai số thập phân",
        layer: "IMPLEMENT",
        status: "LOCKED",
        mastery: null,
        level: 0,
        passed: false,
        pass_now: false,
      }),
    ],
    relations: RELATIONS,
    evidence: [
      {
        sequence_no: 30,
        occurred_at: at,
        node_id: "KC-DEC-CONCEPT",
        dimension: "C",
        score: 1,
        weight: 0.7,
        reason: "ANSWER",
        item_id: "KN-CC-01",
      },
      {
        sequence_no: 41,
        occurred_at: at,
        node_id: "KC-DEC-CONCEPT",
        dimension: "C",
        score: 0,
        weight: 0.55,
        reason: "ANSWER",
        item_id: "KN-CP-01",
      },
    ],
    trace: [
      { sequence_no: 30, occurred_at: at, node_id: "KC-DEC-CONCEPT", mastery: 66.1 },
      { sequence_no: 41, occurred_at: at, node_id: "KC-DEC-CONCEPT", mastery: 58.4 },
    ],
    decisions: [
      {
        sequence_no: 20,
        occurred_at: at,
        action: "ENTER_NODE",
        node_id: "KC-DEC-CONCEPT",
        ref: null,
        support: null,
        rule_ids: ["N-NEXT"],
        reason_codes: ["UNLOCKED"],
      },
      {
        sequence_no: 22,
        occurred_at: at,
        action: "TEACH_THEORY",
        node_id: "KC-DEC-CONCEPT",
        ref: "T1",
        support: null,
        rule_ids: ["N-TEACH"],
        reason_codes: [],
      },
    ],
  };
}
