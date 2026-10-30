import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { WaitingReminder } from "./WaitingReminder";

afterEach(() => vi.useRealTimers());

it("checks in once after quiet time and waits while the learner is composing", async () => {
  vi.useFakeTimers();
  const { rerender } = render(
    <>
      <textarea aria-label="Trả lời" />
      <WaitingReminder enabled turnKey="one" />
    </>,
  );
  await act(() => vi.advanceTimersByTime(44_000));
  expect(screen.queryByRole("status")).toBeNull();
  fireEvent.input(screen.getByRole("textbox"), { target: { value: "Con nghĩ" } });
  await act(() => vi.advanceTimersByTime(45_000));
  expect(screen.queryByRole("status")).toBeNull();
  fireEvent.input(screen.getByRole("textbox"), { target: { value: "" } });
  await act(() => vi.advanceTimersByTime(45_000));
  expect(screen.getByRole("status")).toHaveTextContent("Con đang suy nghĩ");
  fireEvent.pointerDown(document);
  await act(() => vi.advanceTimersByTime(90_000));
  expect(screen.queryByRole("status")).toBeNull();
  rerender(<WaitingReminder enabled={false} turnKey="two" />);
  await act(() => vi.advanceTimersByTime(90_000));
  expect(screen.queryByRole("status")).toBeNull();
});
