import { MicrophoneIcon, XIcon } from "../../../components/icons";
import type { VoiceLive } from "./useVoiceLive";

const PHASE_TEXT: Record<VoiceLive["phase"], string> = {
  off: "",
  speaking: "Cô đang nói…",
  listening: "Cô đang nghe con nói… (nói xong con dừng một chút)",
  hearing: "Cô đang nghe lại lời con…",
  waiting: "",
};

// VOICE-2 (drafted for the owner's review): the child knows it may talk over the tutor.
const SPEAKING_BARGE = "Cô đang nói… con muốn nói thì cứ nói, cô sẽ dừng lại nghe con.";

/**
 * The voice live switch (ADR-030), at the start of the answer row (UI-1: one row instead of a bar of its
 * own). On: a second button to talk now, or to stop the tutor and talk.
 */
export function VoiceToggle({ voice }: { voice: VoiceLive }) {
  if (!voice.available) return null;
  const listening = voice.phase === "listening";
  return (
    <>
      <button
        type="button"
        onClick={voice.toggle}
        aria-pressed={voice.on}
        aria-label={voice.on ? "Tắt nói chuyện" : "Nói chuyện với cô"}
        title={voice.on ? "Tắt nói chuyện" : "Nói chuyện với cô"}
        className={`flex size-11 shrink-0 items-center justify-center rounded-xl text-lg ring-1 ${
          voice.on ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-brand-800 ring-slate-200"
        }`}
      >
        {voice.on ? <XIcon className="size-5" /> : <MicrophoneIcon className="size-5" />}
      </button>
      {voice.on && (
        <button
          type="button"
          onClick={voice.listenNow}
          aria-label={
            listening ? "Dừng nghe" : voice.phase === "speaking" ? "Ngắt lời cô để nói" : "Bấm để nói"
          }
          className={`flex size-11 shrink-0 items-center justify-center rounded-xl ring-1 ${
            listening ? "bg-rose-500 text-white ring-rose-500" : "bg-white ring-slate-200"
          }`}
          style={
            listening
              ? { boxShadow: `0 0 0 ${Math.round(voice.level * 10)}px rgb(244 63 94 / 0.25)` }
              : undefined
          }
        >
          {listening ? <span aria-hidden="true">■</span> : <MicrophoneIcon className="size-5" />}
        </button>
      )}
    </>
  );
}

/** What the tutor is doing while voice is on: speaking, listening, what it heard. One short line. */
export function VoiceStatus({ voice }: { voice: VoiceLive }) {
  if (!voice.available || !voice.on) return null;
  const text =
    voice.problem ??
    (voice.phase === "speaking" && voice.bargeIn
      ? SPEAKING_BARGE
      : PHASE_TEXT[voice.phase] || (voice.heard ? `Cô nghe con nói: «${voice.heard}»` : ""));
  return (
    <p className="mx-auto max-w-3xl truncate px-4 pt-2 text-sm text-slate-600" aria-live="polite">
      {text}
    </p>
  );
}

/** Both parts together (the switch and its status line), where they share a row. */
export function VoiceBar({ voice }: { voice: VoiceLive }) {
  return (
    <>
      <VoiceToggle voice={voice} />
      <VoiceStatus voice={voice} />
    </>
  );
}
