import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Conversation } from "./Conversation";
import type { DisplayTurn } from "./tutorSession";

const sent: DisplayTurn = {
  turn_id: "outgoing",
  sequence_no: 99,
  item_attempt_id: null,
  actor: "student",
  text: "0,9",
  occurred_at: "",
  move: null,
  hint_level: null,
  pending: true,
};

describe("Conversation", () => {
  it("shows the child's message at once and three dots while the tutor prepares (owner, 2026-10-12)", () => {
    render(<Conversation turns={[sent]} typing={null} tutorName="Cô Mây" studentName="An" />);
    expect(screen.getByText("0,9")).toBeInTheDocument();
    expect(screen.queryByText("Đang gửi…")).not.toBeInTheDocument();
    expect(screen.getByTestId("typing")).toBeInTheDocument();
  });

  it("shows no dots when nothing waits", () => {
    render(
      <Conversation
        turns={[{ ...sent, pending: undefined, turn_id: "t1" }]}
        typing={null}
        tutorName="Cô"
        studentName="An"
      />,
    );
    expect(screen.queryByTestId("typing")).not.toBeInTheDocument();
  });
});
