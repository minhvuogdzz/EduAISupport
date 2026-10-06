/**
 * Vietnamese labels for the contract enums. Student-facing wording (activity names) is a draft for the
 * supervising teacher to review; teacher-facing wording keeps the code next to it.
 */
import type {
  ActivityType,
  Dimension,
  HintLevel,
  HintTarget,
  ItemResolution,
  LifecycleState,
  Move,
  NodeStatus,
  Outcome,
  StudentAnnotation,
  TeachAction,
  TeachMessageKind,
} from "../api/contract";

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
