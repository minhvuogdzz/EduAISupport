/**
 * One turn of the child, recorded until a pause (ADR-030): the recording starts at once, stops after
 * ``SILENCE_MS`` of quiet once the child has spoken, or after ``MAX_MS``, or when nothing is said within
 * ``NO_SPEECH_MS``. A plain energy threshold on the microphone, no model.
 */

const SILENCE_MS = 1500;
const MAX_MS = 20_000;
const NO_SPEECH_MS = 8000;
const LOUD = 0.02; // RMS of the signal (0..1) taken as speech

export function canRecord(): boolean {
  return typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
}

/** The recording, or null when the child said nothing. ``onLevel`` gets the loudness 0..1 for a meter. */
export async function recordTurn(
  signal: AbortSignal,
  onLevel: (level: number) => void,
): Promise<Blob | null> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
  });
  const type = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find((t) =>
    MediaRecorder.isTypeSupported(t),
  );
  const recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const audio = new AudioContext();
  const analyser = audio.createAnalyser();
  analyser.fftSize = 1024;
  audio.createMediaStreamSource(stream).connect(analyser);
  const samples = new Float32Array(analyser.fftSize);

  return new Promise((resolve, reject) => {
    const started = performance.now();
    let spoke = false;
    let lastLoud = started;
    let timer = 0;
    const finish = (keep: boolean) => {
      window.clearInterval(timer);
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        void audio.close();
        resolve(keep && spoke && chunks.length ? new Blob(chunks, { type: recorder.mimeType }) : null);
      };
      if (recorder.state !== "inactive") recorder.stop();
      else recorder.onstop(new Event("stop"));
    };
    signal.addEventListener("abort", () => finish(false), { once: true });
    recorder.onerror = () => reject(new Error("recording failed"));
    recorder.start(250);
    timer = window.setInterval(() => {
      analyser.getFloatTimeDomainData(samples);
      const rms = Math.sqrt(samples.reduce((sum, x) => sum + x * x, 0) / samples.length);
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
