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
    const timer = window.setInterval(() => {
      if (gate.push(level.read(), performance.now())) done(true);
    }, 50);
    const done = (heard: boolean) => {
      window.clearInterval(timer);
      level.close();
      resolve(heard);
    };
    if (signal.aborted) done(false);
    else signal.addEventListener("abort", () => done(false), { once: true });
  });
}

/**
 * The recording, or null when the child said nothing. ``onLevel`` gets the loudness 0..1 for a meter.
 * ``stream``: a microphone already open (barge-in), then ``speaking`` says the child is talking already.
 */
export async function recordTurn(
  signal: AbortSignal,
  onLevel: (level: number) => void,
  { stream: given, speaking = false }: { stream?: MediaStream; speaking?: boolean } = {},
): Promise<Blob | null> {
  const stream = given ?? (await openMic());
  const type = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find((t) =>
    MediaRecorder.isTypeSupported(t),
  );
  const recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const level = meter(stream);

  return new Promise((resolve, reject) => {
    const started = performance.now();
    let spoke = speaking;
    let lastLoud = started;
    let timer = 0;
    const finish = (keep: boolean) => {
      window.clearInterval(timer);
      recorder.onstop = () => {
        closeMic(stream);
        level.close();
        resolve(keep && spoke && chunks.length ? new Blob(chunks, { type: recorder.mimeType }) : null);
      };
      if (recorder.state !== "inactive") recorder.stop();
      else recorder.onstop(new Event("stop"));
    };
    signal.addEventListener("abort", () => finish(false), { once: true });
    recorder.onerror = () => reject(new Error("recording failed"));
    recorder.start(250);
    timer = window.setInterval(() => {
      const rms = level.read();
      onLevel(Math.min(1, rms * 8));
      const now = performance.now();
      if (rms > LOUD) {
        spoke = true;
        lastLoud = now;
      }
      if (
        (spoke && now - lastLoud > SILENCE_MS) ||
        now - started > MAX_MS ||
        (!spoke && now - started > NO_SPEECH_MS)
      ) {
        finish(true);
      }
    }, 100);
  });
}
