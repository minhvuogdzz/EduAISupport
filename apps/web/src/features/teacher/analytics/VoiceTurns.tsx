import { useEffect, useRef, useState } from "react";

import { useApi } from "../../../api/apiContext";
import type { TeacherNodeDetail, VoiceTurn } from "../../../api/contract";
import { OUTCOME_LABEL } from "../../../components/labels";
import { formatViDateTime, formatViDecimal } from "../../../lib/viNumber";

/** DI-114: three levels of the listener's confidence q, never shown as a pronunciation score. */
function asrLevel(q: number | null): { label: string; tone: string } {
  if (q === null) return { label: "Chưa có độ tin cậy", tone: "bg-slate-100 text-slate-700 ring-slate-300" };
  if (q >= 0.8) return { label: "Nghe rõ", tone: "bg-emerald-50 text-emerald-900 ring-emerald-200" };
  if (q >= 0.6) return { label: "Nghe tạm", tone: "bg-amber-50 text-amber-900 ring-amber-200" };
  return { label: "Nghe chưa rõ (không trừ điểm)", tone: "bg-rose-50 text-rose-900 ring-rose-200" };
}

const LANGUAGE: Record<VoiceTurn["language"], string> = { en: "Nghe tiếng Anh", vi: "Nghe tiếng Việt" };

/**
 * The child's spoken turns for the teacher (ADR-060 §9.1, DI-114): the question, what the listener wrote
 * (verbatim, never corrected), the language it was told to hear, the ASR level and a button that plays
 * the recording through the teacher-only endpoint (rule F5). Parents never get this list (rule F4).
 */
export function VoiceTurns({ turns, nodes }: { turns: VoiceTurn[]; nodes: TeacherNodeDetail[] }) {
  if (turns.length === 0) return <p className="text-slate-600">Con chưa trả lời bằng giọng nói lần nào.</p>;
  const nodeName = (id: string | null) => nodes.find((n) => n.node_id === id)?.name ?? "";
  const low = turns.filter((t) => t.asr_confidence !== null && t.asr_confidence < 0.6).length;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-slate-700">
        {turns.length} lượt nói gần nhất, {low} lượt nghe chưa rõ.
      </p>
      <ol className="flex flex-col gap-2">
        {turns.map((turn) => {
          const level = asrLevel(turn.asr_confidence);
          return (
            <li key={turn.turn_id} className="voice-turn rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                <span>{formatViDateTime(turn.at)}</span>
                {turn.node_id && <span>· {nodeName(turn.node_id)}</span>}
                <span className="rounded-full bg-white px-2 py-0.5 ring-1 ring-slate-200">
                  {LANGUAGE[turn.language]}
                </span>
                <span className={`rounded-full px-2 py-0.5 font-semibold ring-1 ${level.tone}`}>
                  {level.label}
                  {turn.asr_confidence !== null && ` · q ${formatViDecimal(turn.asr_confidence)}`}
                </span>
                {turn.outcome && (
                  <span className="rounded-full bg-white px-2 py-0.5 ring-1 ring-slate-200">
                    {OUTCOME_LABEL[turn.outcome]}
                  </span>
                )}
                {turn.teacher_override && (
                  <span className="rounded-full bg-sky-50 px-2 py-0.5 font-semibold text-sky-900 ring-1 ring-sky-200">
                    Đã được giáo viên điều chỉnh
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-slate-600">{turn.prompt}</p>
              <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
                <p className="text-base font-semibold text-slate-900">
                  <span className="sr-only">Bản chép lời: </span>
                  <q lang={turn.language}>{turn.transcript}</q>
                </p>
                <PlayButton turn={turn} />
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function PlayButton({ turn }: { turn: VoiceTurn }) {
  const api = useApi();
  const [phase, setPhase] = useState<"idle" | "loading" | "playing" | "failed">("idle");
  const audio = useRef<HTMLAudioElement | null>(null);
  const url = useRef<string | null>(null);
  useEffect(
    () => () => {
      audio.current?.pause();
      if (url.current) URL.revokeObjectURL(url.current);
    },
    [],
  );
  if (!api.getTurnAudio || !turn.audio_ref) {
    return <span className="text-xs text-slate-500">Chưa có ghi âm</span>;
  }
  const play = async () => {
    if (phase === "playing") {
      audio.current?.pause();
      setPhase("idle");
      return;
    }
    setPhase("loading");
    try {
      if (!url.current) url.current = URL.createObjectURL(await api.getTurnAudio!(turn.audio_ref!));
      audio.current ??= new Audio(url.current);
      audio.current.onended = () => setPhase("idle");
      audio.current.currentTime = 0;
      await audio.current.play();
      setPhase("playing");
    } catch {
      setPhase("failed");
    }
  };
  return (
    <span className="flex items-center gap-2">
      {phase === "failed" && <span className="text-xs text-rose-700">Chưa nghe được, cô thử lại nhé.</span>}
      <button
        type="button"
        onClick={() => void play()}
        disabled={phase === "loading"}
        aria-label={`${phase === "playing" ? "Dừng" : "Nghe lại"} lượt nói: ${turn.transcript}`}
        className="min-h-11 rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-brand-800 ring-1 ring-brand-300 hover:bg-brand-50 disabled:opacity-60"
      >
        {phase === "playing" ? "■ Dừng" : phase === "loading" ? "Đang mở…" : "▶ Nghe lại"}
      </button>
    </span>
  );
}
