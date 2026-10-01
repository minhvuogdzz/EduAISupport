/**
 * MOCK ONLY: placeholder wording of the mock tutor. It is NOT approved pedagogy: real tutor text comes
 * from the lesson package (approved by the supervising teacher) through the renderer of T03. Lines keep
 * the constitution's shape anyway: "cô"–"con", short, at most one question, praise effort not talent.
 */
import type { ActivityType } from "../contract";

export const PHRASES = {
  greeting: (name: string, title: string) => `Chào ${name}! Hôm nay cô cùng con học bài “${title}”.`,
  activityIntro: {
    CONCEPT_CHECK: "Trước tiên, cô hỏi con vài câu để xem con đã biết những gì nhé.",
    GUIDED_PRACTICE: "Bây giờ mình cùng luyện tập nhé. Lúc nào cần, con cứ bấm “Xin gợi ý”.",
    EXIT_ASSESSMENT: "Bây giờ là bài kiểm tra cuối buổi. Con tự làm nhé, mỗi câu cô chỉ gợi ý được một lần.",
  } as Partial<Record<ActivityType, string>>,
  /** Blueprint PART 15.2, R-FIRST-WRONG. */
  probe: "Con làm thế nào ra kết quả này?",
  /** Blueprint PART 15.2, R-HELP-REQUEST. */
  offerChoice: "Con muốn gợi ý nhỏ hay xem một ví dụ tương tự?",
  /** What the student "says" when pressing the hint button. */
  hintRequest: "Con xin gợi ý.",
  correct: "Đúng rồi! Mình sang câu tiếp theo nhé.",
  thanksForExplaining: "Cảm ơn con đã giải thích. Mình sang câu tiếp theo nhé.",
  teachBack: "Đúng rồi! Con nói lại cách làm bằng lời của con giúp cô nhé?",
  redirect: "Cô chưa hiểu câu trả lời của con. Con trả lời lại theo yêu cầu của đề giúp cô nhé?",
  nudge: "Con cứ thử trả lời, sai cũng không sao. Con nghĩ thế nào?",
  worked: (steps: string[]) =>
    `Mình cùng làm từng bước nhé. ${steps.join(" ")} Con làm tiếp bước cuối giúp cô nhé?`,
  fullExplanation: (explanation: string) =>
    `${explanation} Con nói lại cách làm bằng lời của con giúp cô nhé?`,
  similarExample: (steps: string[]) =>
    `Cô lấy một ví dụ tương tự nhé. ${steps.join(" ")} Bây giờ con thử lại câu của mình nhé?`,
  moveOn: "Câu này mình sẽ cùng xem lại sau nhé. Mình sang câu tiếp theo.",
  answerRecorded: "Cô đã ghi lại câu trả lời của con.",
  assessmentNoMoreHints: "Ở bài kiểm tra, mỗi câu cô chỉ gợi ý được một lần. Con thử tự làm tiếp nhé?",
  summary: (itemsDone: number) =>
    `Hôm nay con đã làm ${itemsDone} câu. Cô cảm ơn con đã cố gắng suy nghĩ! Buổi học đến đây là kết thúc.`,
};

/** Micro choices offered by OFFER_CHOICE; ids match PART 29 hint preferences (SMALL | EXAMPLE). */
export const HINT_CHOICES = [
  { choice_id: "SMALL", label: "Gợi ý nhỏ" },
  { choice_id: "EXAMPLE", label: "Ví dụ tương tự" },
] as const;
