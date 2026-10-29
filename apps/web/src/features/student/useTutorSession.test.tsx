import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiContext } from "../../api/apiContext";
import type { SessionApi } from "../../api/client";
import type { SessionState } from "../../api/contract";
import { testApi } from "../../test/renderApp";
import { useTutorSession } from "./useTutorSession";

function pending(attempts = 0): SessionState {
  return {
    session_id: "s1",
    state_version: attempts + 1,
    lifecycle_state: "ACTIVE",
    lesson: { lesson_id: "chapter", title: "Số thập phân" },
    student_display_name: "An",
    persona: { tutor_self: "cô", student_address: "con" },
    activity: null,
    item: null,
    pending_choice: null,
    allowed_commands: ["ANSWER"],
    progress: { items_done: 0, items_total: 7 },
    transcript: [],
    tutor_recovery: {
      status: attempts === 3 ? "stopped" : "retrying",
      attempts,
      retry_after_ms: Math.min(2000 * 2 ** attempts, 8000),
      reason: "service",
    },
  };
}

async function setup(recovery: (current: SessionState) => SessionState | Promise<SessionState>) {
  let current = pending();
  const recover = vi.fn(async () => {
    current = await recovery(current);
    return { accepted: true as const, state_version: current.state_version, tutor_turn_id: null };
  });
  const join = vi.fn(() => Promise.resolve(current));
  const submitResponse = vi.fn<SessionApi["submitResponse"]>();
  const api: SessionApi = {
    ...testApi(),
    getState: vi.fn(() => Promise.resolve(current)),
    join,
    recover,
    submitResponse,
  };
  const wrapper = ({ children }: { children: ReactNode }) => <ApiContext value={api}>{children}</ApiContext>;
  const hook = renderHook(() => useTutorSession("s1"), { wrapper });
  await act(async () => {});
  return { ...hook, api, recover, join, submitResponse };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("automatic tutor recovery", () => {
  it("joins an existing lesson and recovers its saved turn without a student message", async () => {
    vi.useFakeTimers();
    const { result, recover, join, submitResponse } = await setup((current) => ({
      ...current,
      state_version: current.state_version + 1,
      tutor_recovery: null,
    }));
    expect(join).toHaveBeenCalledWith("s1");
    expect(result.current.busy).toBe(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(recover).toHaveBeenCalledOnce();
    expect(recover).toHaveBeenCalledWith("s1", 1, "recover-s1-1");
    expect(submitResponse).not.toHaveBeenCalled();
    expect(result.current.busy).toBe(false);
    expect(result.current.view.state?.tutor_recovery).toBeNull();
  });

  it("backs off between attempts and stops when the server reports a lasting failure", async () => {
    vi.useFakeTimers();
    const { result, recover } = await setup((current) => pending(current.tutor_recovery!.attempts + 1));
    for (const delay of [2000, 4000, 8000])
      await act(async () => {
        await vi.advanceTimersByTimeAsync(delay);
      });
    expect(recover).toHaveBeenCalledTimes(3);
    expect(result.current.busy).toBe(false);
    expect(result.current.view.state?.tutor_recovery?.status).toBe("stopped");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(recover).toHaveBeenCalledTimes(3);
  });

  it("also stops when the browser itself cannot reconnect", async () => {
    vi.useFakeTimers();
    const { result, recover } = await setup(() => Promise.reject(new Error("offline")));
    for (const delay of [2000, 5000, 5000])
      await act(async () => {
        await vi.advanceTimersByTimeAsync(delay);
      });
    expect(recover).toHaveBeenCalledTimes(3);
    expect(result.current.busy).toBe(false);
    expect(result.current.view.notice).toContain("Chưa kết nối lại được");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(recover).toHaveBeenCalledTimes(3);
  });

  it("cancels the scheduled recovery when the student leaves", async () => {
    vi.useFakeTimers();
    const { unmount, recover } = await setup((current) => current);
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(recover).not.toHaveBeenCalled();
  });
});
