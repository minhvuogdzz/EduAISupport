/**
 * Vietnamese labels for the contract enums. Student-facing wording (activity names) is a draft for the
 * supervising teacher to review; teacher-facing wording keeps the code next to it.
 */
import type {
  ActivityType,
  HintLevel,
  HintTarget,
  ItemResolution,
  LifecycleState,
  Move,
  Outcome,
  StudentAnnotation,
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

/** "Cô" from the persona's "cô". */
export function capitalize(word: string): string {
  return word.charAt(0).toLocaleUpperCase("vi-VN") + word.slice(1);
}
