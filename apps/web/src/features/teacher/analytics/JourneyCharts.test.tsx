import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ConversationStats, JourneyStep, TeacherNodeDetail } from "../../../api/contract";
import { ConversationPanel } from "./ConversationPanel";
import { JourneyHeatmap } from "./JourneyHeatmap";

const node = (node_id: string, name: string) => ({ node_id, name }) as TeacherNodeDetail;
const step = (node_id: string, resolution: JourneyStep["resolution"], hints = 0): JourneyStep => ({
  node_id,
  item_id: `${node_id}-i`,
  resolution,
  attempts: 1,
  hints,
  at: "2026-10-12T08:00:00Z",
});

describe("the learning heatmap and the conversation panel", () => {
  it("draws one row per period with each item in order, marked and described", () => {
    render(
      <JourneyHeatmap
        nodes={[node("A", "So sánh"), node("B", "Làm tròn")]}
        steps={[
          step("A", "UNRESOLVED"),
          step("A", "SUPPORTED", 2),
          step("A", "INDEPENDENT"),
          step("B", "WORKED"),
        ]}
      />,
    );
    expect(screen.getAllByRole("row")).toHaveLength(2);
    expect(
      screen.getByLabelText(/Câu 2 \(A-i\): Làm được nhờ gợi ý, 1 lần trả lời, 2 gợi ý/),
    ).toBeInTheDocument();
    expect(screen.getByText("Tự làm được (1)")).toBeInTheDocument();
  });

  it("counts how the child typed and what the child said besides answers", () => {
    const stats: ConversationStats = {
      messages: 40,
      hint_button: 3,
      questions: 2,
      parked: 1,
      safety: 0,
      signals: { TEENCODE: 7, UNSTICK: 2 },
      intents: { off_topic: 4 },
    };
    render(<ConversationPanel stats={stats} />);
    expect(screen.getByText("Viết tắt (teen code)").nextSibling?.nextSibling).toHaveTextContent("7");
    expect(screen.getByText("Nói chuyện ngoài bài").nextSibling?.nextSibling).toHaveTextContent("4");
    expect(screen.getByText("Tin nhắn của con").nextSibling).toHaveTextContent("40");
  });
});
