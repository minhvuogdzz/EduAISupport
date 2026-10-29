import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { useApi } from "../../../api/apiContext";
import type { SessionApi } from "../../../api/client";
import type { ChatTurn } from "../../../api/contract";
import { browserSpeak } from "./browserVoice";
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

it("reads the greeting and lesson orientation when voice starts at entry", async () => {
  const greeting: ChatTurn = {
    turn_id: "greeting",
    sequence_no: 1,
    actor: "tutor",
    text: "Cô chào An! Hôm nay mình học số thập phân.",
    item_attempt_id: null,
    occurred_at: "",
    move: null,
    hint_level: null,
    kind: "NODE",
    entry_greeting: true,
  };
  const opening: ChatTurn = {
    ...greeting,
    turn_id: "opening",
    sequence_no: 2,
    text: "Hai phần mười viết là 0,2. Con viết 7/10 thành số thập phân nào?",
    kind: "THEORY",
    entry_greeting: false,
  };
  const hook = renderHook(() => useVoiceLive({ turns: [greeting, opening], canSpeak: false, submit }));
  await act(async () => {});
  act(() => hook.result.current.toggle());
  await act(async () => {});
  expect(vi.mocked(browserSpeak).mock.calls.map((c) => c[0])).toEqual([greeting.text, opening.text]);
});

it("does not repeat an old entry greeting once the student has replied", async () => {
  const base: ChatTurn = {
    turn_id: "g",
    sequence_no: 1,
    actor: "tutor",
    text: "Cô chào An!",
    item_attempt_id: null,
    occurred_at: "",
    move: null,
    hint_level: null,
    entry_greeting: true,
  };
  const conversation: ChatTurn[] = [
    base,
    { ...base, turn_id: "s", sequence_no: 2, actor: "student", text: "con chưa hiểu", entry_greeting: false },
    { ...base, turn_id: "r", sequence_no: 3, text: "Mình xem từng phần nhé?", entry_greeting: false },
  ];
  const hook = renderHook(() => useVoiceLive({ turns: conversation, canSpeak: false, submit }));
  await act(async () => {});
  act(() => hook.result.current.toggle());
  await act(async () => {});
  expect(vi.mocked(browserSpeak).mock.calls.map((c) => c[0])).toEqual([conversation[2].text]);
});
