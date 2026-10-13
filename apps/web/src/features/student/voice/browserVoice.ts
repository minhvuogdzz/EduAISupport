/**
 * The browser's own ear and voice (ADR-030), used when the server has none: the Web Speech API listens in
 * vi-VN, speechSynthesis reads with a Vietnamese voice. Both are optional in browsers, so each is checked.
 */

interface RecognitionResultLike {
  0: { transcript: string };
  isFinal: boolean;
}
interface RecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: { results: ArrayLike<RecognitionResultLike> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type RecognitionCtor = new () => RecognitionLike;

function recognitionCtor(): RecognitionCtor | null {
  const w = globalThis as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function canBrowserListen(): boolean {
  return recognitionCtor() !== null;
}

export function canBrowserSpeak(): boolean {
  return typeof globalThis.speechSynthesis !== "undefined" && typeof SpeechSynthesisUtterance !== "undefined";
}

/** One utterance of the child, as words; "" when nothing was heard. ``onHeard`` shows the words so far. */
export function browserListen(onHeard: (partial: string) => void, signal: AbortSignal): Promise<string> {
  const Ctor = recognitionCtor();
  if (!Ctor) return Promise.reject(new Error("no speech recognition in this browser"));
  return new Promise((resolve, reject) => {
    const rec = new Ctor();
    rec.lang = "vi-VN";
    rec.interimResults = true;
    rec.continuous = false;
    let text = "";
    rec.onresult = (event) => {
      text = Array.from(event.results, (r) => r[0].transcript).join(" ");
      onHeard(text);
    };
    rec.onerror = (event) => {
      if (event.error === "no-speech" || event.error === "aborted") resolve("");
      else reject(new Error(event.error));
    };
    rec.onend = () => resolve(text.trim());
    signal.addEventListener("abort", () => rec.abort(), { once: true });
    rec.start();
  });
}

/** Reads ``text`` with a Vietnamese voice of the browser; resolves when it is done. */
export function browserSpeak(text: string, signal: AbortSignal): Promise<void> {
  if (!canBrowserSpeak()) return Promise.resolve();
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "vi-VN";
    const vi = speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith("vi"));
    if (vi) utterance.voice = vi;
    utterance.rate = 0.95;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    signal.addEventListener(
      "abort",
      () => {
        speechSynthesis.cancel();
        resolve();
      },
      { once: true },
    );
    speechSynthesis.speak(utterance);
  });
}
