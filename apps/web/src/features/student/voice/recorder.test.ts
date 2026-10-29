import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { recordTurn, waitForVoice } from "./recorder";

let rms = 0;
const stopTrack = vi.fn();
const closeAudio = vi.fn();
const getUserMedia = vi.fn();
const stream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;

class FakeRecorder {
  static instances: FakeRecorder[] = [];
  static isTypeSupported = () => true;
  state = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor() {
    FakeRecorder.instances.push(this);
  }
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["audio"]) });
    this.onstop?.();
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  rms = 0;
  FakeRecorder.instances = [];
  stopTrack.mockClear();
  closeAudio.mockClear();
  getUserMedia.mockReset().mockResolvedValue(stream);
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  vi.stubGlobal(
    "AudioContext",
    class {
      createAnalyser() {
        return { fftSize: 1024, getFloatTimeDomainData: (samples: Float32Array) => samples.fill(rms) };
      }
      createMediaStreamSource() {
        return { connect: vi.fn() };
      }
      close = closeAudio;
    },
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("recording actual speech", () => {
  it.each([false, true])("does not send silence (already-open microphone: %s)", async (alreadyOpen) => {
    const recording = recordTurn(new AbortController().signal, vi.fn(), alreadyOpen ? { stream } : {});
    await vi.advanceTimersByTimeAsync(8100);
    expect(await recording).toBeNull();
    expect(stopTrack).toHaveBeenCalledTimes(1);
    expect(closeAudio).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("ignores a short click even though it exceeds the speech volume threshold", async () => {
    const recording = recordTurn(new AbortController().signal, vi.fn());
    rms = 0.1;
    await vi.advanceTimersByTimeAsync(100);
    rms = 0;
    await vi.advanceTimersByTimeAsync(8100);
    expect(await recording).toBeNull();
  });

  it("keeps a short spoken answer and stops after the pause", async () => {
    const recording = recordTurn(new AbortController().signal, vi.fn());
    rms = 0.04;
    await vi.advanceTimersByTimeAsync(250);
    rms = 0;
    await vi.advanceTimersByTimeAsync(1600);
    const audio = await recording;
    expect(audio?.size).toBeGreaterThan(0);
    expect(audio?.type).toBe("audio/webm");
    expect(stopTrack).toHaveBeenCalledTimes(1);
  });

  it("closes a microphone allowed after voice mode was cancelled", async () => {
    let allow!: (stream: MediaStream) => void;
    getUserMedia.mockReturnValue(new Promise((resolve) => (allow = resolve)));
    const controller = new AbortController();
    const recording = recordTurn(controller.signal, vi.fn());
    controller.abort();
    allow(stream);
    expect(await recording).toBeNull();
    expect(stopTrack).toHaveBeenCalledTimes(1);
    expect(FakeRecorder.instances).toHaveLength(0);
  });

  it("discards speech when cancelled and releases the microphone", async () => {
    const controller = new AbortController();
    const recording = recordTurn(controller.signal, vi.fn());
    rms = 0.04;
    await vi.advanceTimersByTimeAsync(300);
    controller.abort();
    expect(await recording).toBeNull();
    expect(stopTrack).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("releases the microphone and meter after a recorder error", async () => {
    const recording = recordTurn(new AbortController().signal, vi.fn());
    const rejected = expect(recording).rejects.toThrow("recording failed");
    await vi.advanceTimersByTimeAsync(50);
    FakeRecorder.instances[0].onerror?.();
    await rejected;
    expect(stopTrack).toHaveBeenCalledTimes(1);
    expect(closeAudio).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("cleans the barge-in meter once even if cancelled after speech was detected", async () => {
    const controller = new AbortController();
    const detected = waitForVoice(stream, controller.signal);
    rms = 0.1;
    await vi.advanceTimersByTimeAsync(400);
    expect(await detected).toBe(true);
    controller.abort();
    expect(closeAudio).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });
});
