/**
 * Vietnamese labels for the contract enums. Student-facing wording (activity names) is a draft for the
 * supervising teacher to review; teacher-facing wording keeps the code next to it.
 */
import type {
  ActivityType,
  AttentionReason,
  Dimension,
  HintLevel,
  HintTarget,
  ItemResolution,
  KcGroup,
  LifecycleState,
  Move,
  NodeStatus,
  Outcome,
  Quality,
  Recommendation,
  StudentAnnotation,
  TeachAction,
  TeachMessageKind,
} from "../api/contract";
import { formatViDecimal } from "../lib/viNumber";

export const ACTIVITY_LABEL: Record<ActivityType, string> = {
  OPENING: "Mở đầu",
  WARMUP_REVIEW: "Ôn bài cũ",
  CONCEPT_CHECK: "Khởi động",
  TEACH: "Học bài mới",
  GUIDED_PRACTICE: "Luyện tập cùng cô",
  INDEPENDENT_PRACTICE: "Tự luyện tập",
  EXIT_ASSESSMENT: "Bài kiểm tra cuối buổi",
  SUMMARY: "Tổng kết",
};

export const MOVE_LABEL: Record<Move, string> = {
  PRESENT: "Nêu câu hỏi",
  PROBE: "Hỏi cách làm",
  HINT: "Gợi ý",
  COGNITIVE_CONFLICT: "Phản ví dụ",
  NUDGE: "Nhắc nhẹ",
  REDIRECT: "Hỏi lại",
  OFFER_CHOICE: "Cho chọn",
  ASK_CONFIRM: "Hỏi xác nhận",
  VERIFY: "Hỏi vì sao",
  CONFIRM_ADVANCE: "Xác nhận đúng",
  WORKED_GUIDANCE: "Cùng làm từng bước",
  FULL_EXPLANATION: "Giải thích đầy đủ",
  TEACH_BACK: "Mời nói lại",
  CLOSE_ITEM: "Đóng câu",
};

/** Names of the hint ladder (comments of HintLevel in pedagogy.py, blueprint PART 15.1). */
export const HINT_LEVEL_LABEL: Record<HintLevel, string> = {
  0: "không gợi ý",
  1: "câu hỏi định hướng",
  2: "nhắc khái niệm",
  3: "gợi ý chiến lược",
  4: "cho một bước",
  5: "chia nhỏ bài",
  6: "cùng làm từng bước",
  7: "giải thích đầy đủ",
};

export const HINT_TARGET_LABEL: Record<HintTarget, string> = {
  TASK: "hiểu đề",
  CONCEPT: "khái niệm",
  STRATEGY: "chiến lược",
  STEP: "bước làm",
  SELF_CHECK: "tự kiểm tra",
  FORMAT: "cách viết",
};

export const OUTCOME_LABEL: Record<Outcome, string> = {
  CORRECT: "Đúng",
  WRONG: "Sai",
  PARTIAL: "Đúng một phần",
  UNPARSEABLE: "Chưa đọc được",
  NEEDS_CONFIRMATION: "Cần xác nhận",
  NEEDS_LLM: "Chờ AI phân tích",
  NO_RESPONSE: "Không trả lời",
  HELP_REQUEST: "Xin trợ giúp",
  ANSWER_DEMAND: "Đòi đáp án",
  CLARIFY_REQUEST: "Hỏi lại đề",
  OFF_TOPIC: "Nói chuyện ngoài bài",
  NEGATIVE_AFFECT: "Nản, mệt",
};

export const RESOLUTION_LABEL: Record<ItemResolution, string> = {
  INDEPENDENT: "Tự làm được",
  SUPPORTED: "Làm được nhờ gợi ý",
  WORKED: "Cần làm mẫu",
  UNRESOLVED: "Chưa giải quyết",
};

export const LIFECYCLE_LABEL: Record<LifecycleState, string> = {
  SCHEDULED: "Đã lên lịch",
  READY: "Sẵn sàng",
  ACTIVE: "Đang học",
  PAUSED: "Tạm dừng",
  INTERRUPTED: "Mất kết nối",
  WRAPPING_UP: "Đang kết thúc",
  COMPLETED: "Đã xong",
  EXITED: "Đã thoát",
  INCOMPLETE: "Chưa hoàn thành",
  MISSED: "Vắng",
  CANCELLED: "Đã hủy",
  FAILED: "Lỗi hệ thống",
};

export const STUDENT_KIND_LABEL: Record<StudentAnnotation["kind"], string> = {
  ANSWER: "Trả lời",
  STEP: "Bước làm",
  EXPLANATION: "Giải thích",
  MESSAGE: "Tin nhắn",
  HINT_REQUEST: "Bấm xin gợi ý",
  CHOICE: "Chọn",
};

// ---------------------------------------------------------------- teaching on the knowledge graph (M1-7)

export const NODE_STATUS_LABEL: Record<NodeStatus, string> = {
  PASSED: "Đã qua",
  CURRENT: "Đang học",
  ON_HOLD: "Chờ ôn bài nền",
  STOPPED: "Cần học lại",
  AVAILABLE: "Sẵn sàng",
  LOCKED: "Chưa mở",
};

/** The teaching cycle (plan v1, 5.2), step 1 to 7. Student-facing wording: draft for the teacher. */
export const TEACHING_STEPS = [
  "Ôn bài nền",
  "Giảng bài",
  "Kiểm tra hiểu",
  "Học cách làm",
  "Luyện tập",
  "Vận dụng",
  "Qua bài",
] as const;

/** Levels of understanding 0–5 (blueprint §4–§8), in words for the student. */
export const LEVEL_LABEL = [
  "Mới bắt đầu",
  "Nhận biết",
  "Làm theo mẫu",
  "Hiểu bài",
  "Vận dụng được",
  "Thành thạo",
] as const;

export const TEACH_KIND_LABEL: Record<TeachMessageKind, string> = {
  NODE: "Chuyển bài",
  THEORY: "Giảng bài",
  EXAMPLE: "Cô làm mẫu",
  RETELL_PROMPT: "Mời nói lại",
  FEEDBACK: "Nhận xét",
  PASS: "Qua bài",
  STOP: "Dừng bài",
  SUMMARY: "Tổng kết",
};

export const TEACH_ACTION_LABEL: Record<TeachAction, string> = {
  ENTER_NODE: "Vào bài",
  WARMUP_ITEM: "Câu ôn bài nền",
  SWITCH_TO_PREREQUISITE: "Quay về bài nền",
  TEACH_THEORY: "Giảng lý thuyết",
  CHECK_ITEM: "Câu kiểm tra hiểu",
  ASK_RETELL: "Mời nói lại",
  SHOW_WORKED_EXAMPLE: "Làm mẫu",
  COMPLETION_ITEM: "Bài cùng làm",
  PRACTICE_ITEM: "Bài luyện tập",
  TRANSFER_ITEM: "Bài vận dụng",
  REVIEW_ITEM: "Câu ôn xen kẽ",
  PASS_NODE: "Qua bài",
  STOP_NODE: "Dừng bài",
  FINISH: "Kết thúc buổi",
};

/** Teacher-facing: the dimensions of the math framework (blueprint PART 26.1), code kept beside. */
export const DIMENSION_LABEL: Record<Dimension, string> = {
  C: "Làm đúng",
  R: "Lập luận",
  A: "Vận dụng",
  T: "Chuyển giao",
  I: "Tự làm",
  S: "Ghi nhớ",
  D: "Phát hiện lỗi",
};

/** Weights of M (blueprint §20); a dimension without enough evidence is left out (DI-1). */
export const DIMENSION_WEIGHT: Record<Dimension, number> = {
  C: 0.2,
  R: 0.2,
  A: 0.15,
  T: 0.15,
  I: 0.1,
  S: 0.1,
  D: 0.1,
};

export const EVIDENCE_REASON_LABEL: Record<string, string> = {
  ANSWER: "kết quả câu",
  INDEPENDENCE: "mức tự làm",
  NO_EXPLANATION: "không giải thích",
  GUESS: "đoán",
  CONCEPTUAL_ERROR: "lỗi khái niệm",
  EXPLANATION: "trả lời vì sao",
  RETELL: "nói lại quy tắc",
};

/** What a node still lacks before it can be passed (DI-15). */
export const MISSING_LABEL: Record<string, string> = {
  MASTERY: "Điểm M chưa tới ngưỡng",
  UNDERSTOOD: "Chưa đủ bằng chứng hiểu bài",
  EXPLANATION: "Chưa giải thích được",
  APPLICATION: "Chưa làm đúng bài vận dụng",
  MISCONCEPTION: "Còn lỗi sai nghiêm trọng",
};

/** DI-14 for parents (words, never a score). NOT_STARTED is added for topics not begun. */
export const QUALITY_LABEL: Record<Quality, string> = {
  NOT_STARTED: "Chưa học",
  INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
  FAMILIAR: "Đang làm quen",
  WITH_SUPPORT: "Làm được khi có hỗ trợ",
  INDEPENDENT: "Tự làm được",
  SOLID: "Vững và vận dụng",
};

/** What each state means, for the parent (one sentence each). */
export const QUALITY_MEANING: Record<Quality, string> = {
  NOT_STARTED: "Con chưa học tới bài này.",
  INSUFFICIENT_DATA: "Con mới làm ít câu, cô chưa đủ căn cứ để nhận xét.",
  FAMILIAR: "Con đang làm quen, còn cần cô hướng dẫn nhiều.",
  WITH_SUPPORT: "Con làm được khi có gợi ý của cô.",
  INDEPENDENT: "Con tự làm được và giải thích được cách làm.",
  SOLID: "Con làm vững và vận dụng được vào bài mới.",
};

/** The student's two words for a topic (PART 27.1): "Đã nắm chắc" or "Cần luyện thêm". */
export function studentWords(quality: Quality, status?: NodeStatus): string {
  if (quality === "INDEPENDENT" || quality === "SOLID") return "Đã nắm chắc";
  if (quality === "NOT_STARTED") return status === "CURRENT" ? "Đang học" : "Chưa học";
  return "Cần luyện thêm";
}

/** The topic being learned but not graded yet reads "Đang học", not "Chưa học". */
export function topicState(node: { quality: Quality; status: NodeStatus }): {
  label: string;
  meaning: string;
  tone: string;
} {
  if (node.quality === "NOT_STARTED" && node.status === "CURRENT") {
    return {
      label: "Đang học",
      meaning: "Con đang học bài này, cô chưa đủ căn cứ để nhận xét.",
      tone: "bg-brand-50 text-brand-900 ring-brand-200",
    };
  }
  return {
    label: QUALITY_LABEL[node.quality],
    meaning: QUALITY_MEANING[node.quality],
    tone: QUALITY_TONE[node.quality],
  };
}

/** Learning time: never "0 phút" once the student has learned something. */
export function minutesText(minutes: number, sessions: number): string {
  return minutes === 0 && sessions > 0 ? "dưới 1 phút" : `${minutes} phút`;
}

/** Chip colors of the qualitative states: a status, so always shown with its words. */
export const QUALITY_TONE: Record<Quality, string> = {
  NOT_STARTED: "bg-slate-100 text-slate-600 ring-slate-200",
  INSUFFICIENT_DATA: "bg-slate-100 text-slate-700 ring-slate-300",
  FAMILIAR: "bg-sky-50 text-sky-900 ring-sky-200",
  WITH_SUPPORT: "bg-amber-50 text-amber-900 ring-amber-200",
  INDEPENDENT: "bg-emerald-50 text-emerald-900 ring-emerald-200",
  SOLID: "bg-emerald-600 text-white ring-emerald-600",
};

/** Rules of the node teaching policy (plan v1, 5.4). */
export const RULE_LABEL: Record<string, string> = {
  "N-NEXT": "Chọn bài tiếp theo",
  "N-WARMUP": "Ôn bài nền",
  "N-TEACH": "Giảng bài",
  "N-CHECK": "Kiểm tra hiểu",
  "N-RETEACH": "Giảng lại cách khác",
  "N-METHOD": "Dạy cách làm",
  "N-PRACTICE": "Luyện tập",
  "N-TRANSFER": "Vận dụng",
  "N-PASS": "Qua bài",
  "N-REVIEW": "Ôn xen kẽ",
  "N-REMEDIATE": "Quay về bài nền",
  "N-BUDGET": "Dừng bài",
  "N-FINISH": "Kết thúc",
};

/** "Cô" from the persona's "cô". */
export function capitalize(word: string): string {
  return word.charAt(0).toLocaleUpperCase("vi-VN") + word.slice(1);
}

// ---------------------------------------------------------------- the teacher's analytics (PART 27, §56)

/** The six levels of understanding with the names of the Math framework (§4–§8), for the teacher. */
export const LEVEL_NAME = [
  "Chưa hình thành kiến thức",
  "Nhận biết",
  "Thực hiện theo quy trình",
  "Hiểu bản chất",
  "Vận dụng",
  "Làm chủ",
] as const;

/** §43: mastered ✓, not yet stable ⚠, weak ✕ (DI-27), plus the KCs without enough evidence. */
export const KC_GROUP_LABEL: Record<KcGroup, string> = {
  PASSED: "Đã qua bài",
  UNSTABLE: "Chưa ổn định",
  WEAK: "Còn yếu",
  INSUFFICIENT: "Chưa đủ dữ liệu",
  NOT_STARTED: "Chưa học",
};

export const KC_GROUP_MARK: Record<KcGroup, string> = {
  PASSED: "✓",
  UNSTABLE: "⚠",
  WEAK: "✕",
  INSUFFICIENT: "?",
  NOT_STARTED: "–",
};

/** The tutor's next move by the band of M: DI-8 (blueprint 26.1), waiting for the owner's approval. */
export const RECOMMENDATION_LABEL: Record<Recommendation, string> = {
  DIAGNOSE: "Hỏi một câu chẩn đoán để biết con đang ở đâu",
  EXPLAIN: "Giảng ngắn rồi làm mẫu (Micro Explain → Guided Example)",
  GUIDED: "Hỏi gợi mở, gợi ý sớm (Guided Question)",
  PRACTICE: "Cho tự luyện và hỏi “vì sao” (Independent Practice)",
  TRANSFER: "Cho bài biến thể, bài chuyển giao (Transfer)",
  CHALLENGE: "Cho bài thử thách hoặc sang bài tiếp theo (Challenge)",
};

/** §27: progress, standing still, decline (DI-24: against the score three changes earlier). */
export const DIRECTION_LABEL: Record<"UP" | "FLAT" | "DOWN", string> = {
  UP: "↗ Tiến bộ",
  FLAT: "→ Đứng yên",
  DOWN: "↘ Suy giảm",
};

/** One sentence per reason the teacher should look at a student (DI-20). */
export function attentionText(
  reason: AttentionReason,
  nodeName: (id: string) => string,
  misconceptionName: (id: string) => string,
): string {
  const node = reason.node_id ? nodeName(reason.node_id) : "";
  switch (reason.kind) {
    case "STOPPED":
      return `Gia sư đã dừng bài “${node}”: cần cô giáo hỗ trợ trực tiếp`;
    case "MISCONCEPTION":
      return `Lặp lại lỗi “${misconceptionName(reason.misconception_id ?? "")}” (${reason.count ?? 0} lần)`;
    case "WEAK":
      return `Bài “${node}” còn yếu: M ${formatViDecimal(reason.mastery ?? 0)}`;
    default:
      return `Buổi học còn dở, ${reason.days ?? 0} ngày chưa quay lại`;
  }
}
