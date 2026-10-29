import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { useApi } from "../../../api/apiContext";
import type { SessionApi } from "../../../api/client";
import { recordTurn } from "./recorder";
import { useVoiceLive } from "./useVoiceLive";

vi.mock("../../../api/apiContext", () => ({ useApi: vi.fn() }));
vi.mock("./recorder", () => ({
  canRecord: () => true,
  recordTurn: vi.fn(),
  closeMic: vi.fn(),
  openMic: vi.fn(),
  waitForVoice: vi.fn(),
}));
vi.mock("./browserVoice", () => ({
  canBrowserSpeak: () => true,
  canBrowserListen: () => false,
  browserListen: vi.fn(),
  browserSpeak: vi.fn(),
}));

const transcribe = vi.fn();
const submit = vi.fn();
const turns: [] = [];

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  vi.mocked(useApi).mockReturnValue({
    voice: { status: () => Promise.resolve({ listen: true, speak: false, speech_model: null }), transcribe },
  } as unknown as SessionApi);
  submit.mockResolvedValue(true);
});
afterEach(() => vi.useRealTimers());

async function enableVoice() {
  const hook = renderHook(() => useVoiceLive({ turns, canSpeak: true, submit }));
  await act(async () => {});
  act(() => hook.result.current.toggle());
  await act(async () => vi.advanceTimersByTimeAsync(350));
  return hook;
}

it("does not transcribe or submit a recording with no speech", async () => {
  vi.mocked(recordTurn).mockResolvedValue(null);
  const hook = await enableVoice();
  expect(recordTurn).toHaveBeenCalledTimes(1);
  expect(transcribe).not.toHaveBeenCalled();
  expect(submit).not.toHaveBeenCalled();
  expect(hook.result.current.problem).toBe("Cô chưa nghe rõ, con nói lại nhé.");
});

it("does not submit words rejected by the server's no-speech check", async () => {
  vi.mocked(recordTurn).mockResolvedValue(new Blob(["audio"]));
  transcribe.mockResolvedValue({ text: "", model: "whisper-large-v3" });
  const hook = await enableVoice();
  expect(transcribe).toHaveBeenCalledTimes(1);
  expect(submit).not.toHaveBeenCalled();
  expect(hook.result.current.heard).toBe("");
});

it("submits a real short answer once with voice modality", async () => {
  vi.mocked(recordTurn).mockResolvedValue(new Blob(["audio"]));
  transcribe.mockResolvedValue({ text: "không phẩy một", model: "whisper-large-v3" });
  await enableVoice();
  expect(submit).toHaveBeenCalledExactlyOnceWith("không phẩy một", "VOICE");
});

it("ignores a transcription arriving after voice was turned off", async () => {
  vi.mocked(recordTurn).mockResolvedValue(new Blob(["audio"]));
  let respond!: (value: { text: string }) => void;
  transcribe.mockReturnValue(new Promise((resolve) => (respond = resolve)));
  const hook = await enableVoice();
  act(() => hook.result.current.toggle());
  await act(async () => {
    respond({ text: "cảm ơn" });
    await Promise.resolve();
  });
  expect(submit).not.toHaveBeenCalled();
  expect(hook.result.current.phase).toBe("off");
});
