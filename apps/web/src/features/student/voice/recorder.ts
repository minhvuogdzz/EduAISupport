/**
 * One turn of the child, recorded until a pause (ADR-030): the recording starts at once, stops after
 * ``SILENCE_MS`` of quiet once the child has spoken, or after ``MAX_MS``, or when nothing is said within
 * ``NO_SPEECH_MS``. A plain energy threshold on the microphone, no model.
 *
 * Barge-in (VOICE-2): while the tutor speaks, ``waitForVoice`` listens for the child talking over it. The
 * tutor's own voice comes back through the microphone, cancelled by the browser's echo cancellation but
 * not always fully, so the threshold is higher (``BARGE_LOUD``) and the voice has to last ``BARGE_MS``.
 */

const SILENCE_MS = 1500;
const MAX_MS = 20_000;
const NO_SPEECH_MS = 8000;
const LOUD = 0.02; // RMS of the signal (0..1) taken as speech
const SPEECH_MS = 150; // DI (VOICE-3): a click or microphone startup pop is not an utterance
export const BARGE_LOUD = 0.06; // DI (VOICE-2): the child talking over the tutor, louder than its echo
export const BARGE_MS = 300; // DI (VOICE-2): ...for this long without a break

export function canRecord(): boolean {
  return typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
}

/** Speech that lasts: true once the level stayed above ``threshold`` for ``sustainMs`` in a row. */
export class SpeechGate {
  private since: number | null = null;
  private readonly threshold: number;
  private readonly sustainMs: number;

  constructor(threshold = BARGE_LOUD, sustainMs = BARGE_MS) {
    this.threshold = threshold;
    this.sustainMs = sustainMs;
  }

  push(rms: number, now: number): boolean {
    if (rms <= this.threshold) {
      this.since = null;
      return false;
    }
    this.since ??= now;
    return now - this.since >= this.sustainMs;
  }
}

export function openMic(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
}

export function closeMic(stream: MediaStream): void {
  stream.getTracks().forEach((t) => t.stop());
}

/** The loudness of the microphone, read on demand (RMS 0..1). */
function meter(stream: MediaStream): { read: () => number; close: () => void } {
  const audio = new AudioContext();
  const analyser = audio.createAnalyser();
  analyser.fftSize = 1024;
  audio.createMediaStreamSource(stream).connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  return {
    read() {
      analyser.getFloatTimeDomainData(samples);
      return Math.sqrt(samples.reduce((sum, x) => sum + x * x, 0) / samples.length);
    },
    close() {
      void audio.close();
    },
  };
}

/** True when the child starts talking (barge-in), false when ``signal`` ends the wait first. */
export function waitForVoice(stream: MediaStream, signal: AbortSignal): Promise<boolean> {
  const level = meter(stream);
  const gate = new SpeechGate();
  return new Promise((resolve) => {
    let settled = false;
    const timer = window.setInterval(() => {
      if (gate.push(level.read(), performance.now())) done(true);
    }, 50);
    const done = (heard: boolean) => {
      if (settled) return;
      settled = true;
      window.clearInterval(timer);
      signal.removeEventListener("abort", cancel);
      level.close();
      resolve(heard);
    };
    const cancel = () => done(false);
    if (signal.aborted) done(false);
    else signal.addEventListener("abort", cancel, { once: true });
  });
}

/**
 * The recording, or null when the child said nothing. ``onLevel`` gets the loudness 0..1 for a meter.
 * ``stream``: a microphone already open (barge-in). It still needs speech in this recording.
 */
export async function recordTurn(
  signal: AbortSignal,
  onLevel: (level: number) => void,
  { stream: given }: { stream?: MediaStream } = {},
): Promise<Blob | null> {
  if (signal.aborted) {
    if (given) closeMic(given);
    return null;
  }
  const stream = given ?? (await openMic());
  // Permission may have been pending when voice mode was switched off.
  if (signal.aborted) {
    closeMic(stream);
    return null;
  }
  const type = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find((t) =>
    MediaRecorder.isTypeSupported(t),
  );
  let recorder: MediaRecorder;
  let level: ReturnType<typeof meter>;
  try {
    recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
    level = meter(stream);
  } catch (error) {
    closeMic(stream);
    throw error;
  }
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  return new Promise((resolve, reject) => {
    const started = performance.now();
    const gate = new SpeechGate(LOUD, SPEECH_MS);
    let spoke = false;
    let lastLoud = started;
    let timer = 0;
    let finishing = false;
    let settled = false;
    let keepAudio = false;
    let failure: Error | undefined;
    recorder.onstop = () => {
      if (settled) return;
      settled = true;
      finishing = true;
      window.clearInterval(timer);
      signal.removeEventListener("abort", cancel);
      closeMic(stream);
      level.close();
      if (failure) reject(failure);
      else
        resolve(
          keepAudio && !signal.aborted && spoke && chunks.length
            ? new Blob(chunks, { type: recorder.mimeType })
            : null,
        );
    };
    const finish = (keep: boolean, error?: Error) => {
      if (finishing) return;
      finishing = true;
      keepAudio = keep;
      failure = error;
      window.clearInterval(timer);
      if (recorder.state !== "inactive") recorder.stop();
      else recorder.onstop?.(new Event("stop"));
    };
    const cancel = () => finish(false);
    signal.addEventListener("abort", cancel, { once: true });
    recorder.onerror = () => finish(false, new Error("recording failed"));
    try {
      recorder.start(250);
    } catch (error) {
      finish(false, error instanceof Error ? error : new Error("recording failed"));
    }
    if (finishing) return;
    timer = window.setInterval(() => {
      const rms = level.read();
      onLevel(Math.min(1, rms * 8));
      const now = performance.now();
      if (gate.push(rms, now)) spoke = true;
      if (rms > LOUD) lastLoud = now;
      if (
        (spoke && now - lastLoud > SILENCE_MS) ||
        now - started > MAX_MS ||
        (!spoke && now - started > NO_SPEECH_MS)
      ) {
        finish(true);
      }
    }, 50);
  });
}
