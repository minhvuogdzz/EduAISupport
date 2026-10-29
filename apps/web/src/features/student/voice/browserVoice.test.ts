import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { browserListen } from "./browserVoice";

class Recognition {
  static latest: Recognition;
  onresult: ((event: { results: { 0: { transcript: string }; isFinal: boolean }[] }) => void) | null = null;
  onend: (() => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  start = vi.fn();
  abort = vi.fn();
  constructor() {
    Recognition.latest = this;
  }
}

beforeEach(() => vi.stubGlobal("SpeechRecognition", Recognition));
afterEach(() => vi.unstubAllGlobals());

it("shows interim words but never submits them if recognition ends without a final result", async () => {
  const heard = vi.fn();
  const words = browserListen(heard, new AbortController().signal);
  Recognition.latest.onresult?.({ results: [{ 0: { transcript: "cảm ơn" }, isFinal: false }] });
  expect(heard).toHaveBeenCalledWith("cảm ơn");
  Recognition.latest.onend?.();
  expect(await words).toBe("");
});

it("returns only confirmed words when final and interim results coexist", async () => {
  const words = browserListen(vi.fn(), new AbortController().signal);
  Recognition.latest.onresult?.({
    results: [
      { 0: { transcript: "không phẩy một" }, isFinal: true },
      { 0: { transcript: "hẹn gặp lại" }, isFinal: false },
    ],
  });
  Recognition.latest.onend?.();
  expect(await words).toBe("không phẩy một");
});

it("discards confirmed words too when the user turns voice off before recognition ends", async () => {
  const controller = new AbortController();
  const words = browserListen(vi.fn(), controller.signal);
  const rec = Recognition.latest;
  rec.onresult?.({ results: [{ 0: { transcript: "một" }, isFinal: true }] });
  controller.abort();
  rec.onend?.();
  expect(await words).toBe("");
  expect(rec.abort).toHaveBeenCalledTimes(1);
});
