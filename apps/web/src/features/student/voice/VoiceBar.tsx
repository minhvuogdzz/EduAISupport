import type { VoiceLive } from "./useVoiceLive";

const PHASE_TEXT: Record<VoiceLive["phase"], string> = {
  off: "",
  speaking: "Cô đang nói…",
  listening: "Cô đang nghe con nói… (nói xong con dừng một chút)",
  hearing: "Cô đang nghe lại lời con…",
  waiting: "",
};

/** The voice live switch and what the tutor is doing: speaking, listening, what it heard (ADR-030). */
export function VoiceBar({ voice }: { voice: VoiceLive }) {
  if (!voice.available) return null;
  const listening = voice.phase === "listening";
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-2" aria-live="polite">
      <button
        type="button"
        onClick={voice.toggle}
        aria-pressed={voice.on}
        className={`rounded-2xl px-3 py-1.5 text-sm font-semibold ring-1 ${
          voice.on ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-brand-800 ring-brand-200"
        }`}
      >
        {voice.on ? "Tắt nói chuyện" : "🎤 Nói chuyện với cô"}
      </button>
      {voice.on && (
        <button
          type="button"
          onClick={voice.listenNow}
          aria-label={listening ? "Dừng nghe" : "Bấm để nói"}
          className={`flex size-9 items-center justify-center rounded-full ring-1 ${
            listening ? "bg-rose-500 text-white ring-rose-500" : "bg-white ring-slate-300"
          }`}
          style={
            listening
              ? { boxShadow: `0 0 0 ${Math.round(voice.level * 10)}px rgb(244 63 94 / 0.25)` }
              : undefined
          }
        >
          {listening ? "■" : "🎤"}
        </button>
      )}
      {voice.on && (
        <p className="min-w-0 flex-1 truncate text-sm text-slate-700">
          {voice.problem ??
            (PHASE_TEXT[voice.phase] || (voice.heard ? `Cô nghe con nói: «${voice.heard}»` : ""))}
        </p>
      )}
    </div>
  );
}
