import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Conversation } from "./Conversation";

afterEach(() => vi.useRealTimers());

describe("quiet model fallback", () => {
  it("keeps thinking visible across a long request, then replaces it with the final reply", async () => {
    vi.useFakeTimers();
    const props = { turns: [], typing: null, tutorName: "Cô", studentName: "An" };
    const { rerender, unmount } = render(<Conversation {...props} waiting />);
    expect(screen.getByRole("status")).toHaveTextContent("Cô đang suy nghĩ…");
    await act(() => vi.advanceTimersByTime(8000));
    expect(screen.getByRole("status")).toHaveTextContent("Cô đang suy nghĩ, con chờ một chút nhé.");
    expect(screen.getByRole("log")).toBeEmptyDOMElement();
    // Ack can precede the next snapshot: waiting remains until a reply is available.
    rerender(<Conversation {...props} waiting />);
    expect(screen.getByTestId("typing")).toBeInTheDocument();
    rerender(
      <Conversation
        {...props}
        waiting
        typing={{ turn_id: "answer", text: "Con thử so sánh phần nguyên nhé." }}
      />,
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByTestId("typing")).toHaveTextContent("Con thử so sánh phần nguyên nhé.");
    rerender(<Conversation {...props} waiting={false} />);
    expect(screen.queryByTestId("typing")).not.toBeInTheDocument();
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("cancels the long-wait reminder when the request finishes quickly", async () => {
    vi.useFakeTimers();
    const props = { turns: [], typing: null, tutorName: "Cô", studentName: "An" };
    const { rerender } = render(<Conversation {...props} waiting />);
    await act(() => vi.advanceTimersByTime(1000));
    rerender(<Conversation {...props} waiting={false} />);
    await act(() => vi.advanceTimersByTime(10000));
    expect(screen.queryByText(/con chờ một chút/)).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
