import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAutoAdvance } from "./useAutoAdvance";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
describe("Buddy's two second rotation", () => {
  it("advances every two seconds, resets after a manual choice, and pauses only with the explicit control", () => {
    vi.useFakeTimers();
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const { result, unmount } = renderHook(() => useAutoAdvance(5));
    act(() => {
      vi.advanceTimersByTime(1999);
    });
    expect(result.current.selected).toBe(0);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current.selected).toBe(1);
    act(() => result.current.setSelected(4));
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(result.current.selected).toBe(0);
    act(() => result.current.setPlaying(false));
    act(() => {
      vi.advanceTimersByTime(6000);
    });
    expect(result.current.selected).toBe(0);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
  it("keeps manual selection available without auto rotation for reduced motion", () => {
    vi.useFakeTimers();
    vi.stubGlobal("matchMedia", () => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const { result } = renderHook(() => useAutoAdvance(5));
    act(() => {
      vi.advanceTimersByTime(8000);
    });
    expect(result.current.selected).toBe(0);
    act(() => result.current.setSelected(3));
    expect(result.current.selected).toBe(3);
    expect(result.current.running).toBe(false);
  });
});

it("continues changing Buddy's expression while hovered and focused", async () => {
  const { render, screen, fireEvent } = await import("@testing-library/react");
  const { BuddyShowcase } = await import("../pages/BuddyShowcase");
  vi.useFakeTimers();
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
  render(<BuddyShowcase />);
  const moods = screen.getByRole("group", { name: "Khám phá biểu cảm Monkey Buddy" });
  fireEvent.mouseEnter(moods);
  fireEvent.focus(screen.getByRole("button", { name: "Chào con" }));
  act(() => {
    vi.advanceTimersByTime(2000);
  });
  expect(screen.getByRole("button", { name: "Lắng nghe" })).toHaveAttribute("aria-pressed", "true");
  act(() => {
    vi.advanceTimersByTime(2000);
  });
  expect(screen.getByRole("button", { name: "Cùng suy nghĩ" })).toHaveAttribute("aria-pressed", "true");
});
