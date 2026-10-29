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
  if (signal.aborted) return Promise.resolve("");
  const Ctor = recognitionCtor();
  if (!Ctor) return Promise.reject(new Error("no speech recognition in this browser"));
  return new Promise((resolve, reject) => {
    const rec = new Ctor();
    rec.lang = "vi-VN";
    rec.interimResults = true;
    rec.continuous = false;
    let finalText = "";
    const done = (text: string, error?: Error) => {
      rec.onresult = rec.onerror = rec.onend = null;
      signal.removeEventListener("abort", cancel);
      if (error) reject(error);
      else resolve(text.trim());
    };
    const cancel = () => {
      done("");
      rec.abort();
    };
    rec.onresult = (event) => {
      const results = Array.from(event.results);
      finalText = results
        .filter((r) => r.isFinal)
        .map((r) => r[0].transcript)
        .join(" ");
      onHeard(results.map((r) => r[0].transcript).join(" "));
    };
    rec.onerror = (event) => {
      if (event.error === "no-speech" || event.error === "aborted") done("");
      else done("", new Error(event.error));
    };
    rec.onend = () => done(finalText);
    signal.addEventListener("abort", cancel, { once: true });
    try {
      rec.start();
    } catch (error) {
      done("", error instanceof Error ? error : new Error("speech recognition failed"));
    }
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
