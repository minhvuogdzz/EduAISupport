import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SessionTranscript, TranscriptTurn } from "../../api/contract";
import { TranscriptView } from "./TranscriptView";

function turn(sequence_no: number, text: string, teach: TranscriptTurn["teach"]): TranscriptTurn {
  return {
    sequence_no,
    occurred_at: "2026-10-07T08:00:00Z",
    actor: "tutor",
    text,
    tutor: null,
    student: null,
    teach,
  };
}

const TRANSCRIPT: SessionTranscript = {
  session: {
    session_id: "s1",
    student_display_name: "Minh",
    lesson_title: "Số thập phân",
    lifecycle_state: "ACTIVE",
    started_at: "2026-10-07T08:00:00Z",
    updated_at: "2026-10-07T08:10:00Z",
    progress: { items_done: 0, items_total: 7 },
    misconception_ids: [],
    engine: "live",
    mode: "CHAPTER",
  },
  segments: [
    {
      kind: "session",
      turns: [
        turn(1, "Phần nguyên là chữ số đứng bên trái dấu phẩy. Mình quay lại câu của cô nhé: …", {
          kind: "ANSWER",
          node_id: "KC-DEC-CONCEPT",
          rule_ids: [],
          reason_codes: [],
          source: "LLM",
          sources: ["Khái niệm số thập phân · phương pháp"],
          rejected: [["UNSUPPORTED_CLAIM"]],
          grounded: true,
          grounding: "cosine 0.78 ≥ 0.65",
          parked: null,
        }),
        {
          sequence_no: 3,
          occurred_at: "2026-10-07T08:02:00Z",
          actor: "student",
          text: "cô ơi con bị bạn đánh",
          tutor: null,
          teach: null,
          student: {
            kind: "ANSWER",
            outcome: null,
            normalized_answer: null,
            misconception: null,
            safety: true,
            read: { label: "ASKS_ABOUT", focus: "mẫu", source: "LLM" },
          },
        },
        turn(2, "Cô chưa tìm được câu trả lời chắc chắn trong tài liệu của bài…", {
          kind: "ANSWER",
          node_id: "KC-DEC-CONCEPT",
          rule_ids: [],
          reason_codes: [],
          source: "TEMPLATE",
          sources: [],
          rejected: [],
          grounded: false,
          grounding: "cosine 0.58 < 0.65",
          parked: "NOT_GROUNDED",
        }),
      ],
    },
  ],
};

describe("teacher transcript of grounded speech (RAG-2)", () => {
  it("shows who wrote each answer, what it rests on and why a question was kept", () => {
    render(<TranscriptView transcript={TRANSCRIPT} />);
    expect(screen.getAllByText("Trả lời câu con hỏi")).toHaveLength(2);
    expect(screen.getByText("Qwen viết, đã kiểm chứng với nguồn")).toBeInTheDocument();
    expect(screen.getByText("Có căn cứ (cosine 0.78 ≥ 0.65)")).toBeInTheDocument();
    expect(screen.getByText("Nguồn: Khái niệm số thập phân · phương pháp")).toBeInTheDocument();
    expect(screen.getByText("Qwen bị chặn 1 lần: UNSUPPORTED_CLAIM")).toBeInTheDocument();
    expect(screen.getByText("Không có căn cứ (cosine 0.58 < 0.65)")).toBeInTheDocument();
    expect(screen.getByText("Tài liệu và nguồn tra cứu chưa trả lời được: để lại cho giáo viên")).toBeInTheDocument();
    expect(screen.getByText("Đáng lo: cô cần đọc kỹ câu này")).toBeInTheDocument();
    expect(screen.getByText("Gia sư hiểu: con hỏi về «mẫu» (Qwen đọc)")).toBeInTheDocument();
  });
});
