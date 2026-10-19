import { memo } from "react";

import { BookIcon, LightbulbIcon, PencilIcon, StarIcon } from "../../components/icons";
import { TEACH_KIND_LABEL } from "../../components/labels";
import { Mascot } from "../../components/Mascot";
import { MathText } from "../../components/MathText";
import type { DisplayTurn, TutorView } from "./tutorSession";

interface ConversationProps {
  turns: DisplayTurn[];
  typing: TutorView["typing"];
  tutorName: string;
  studentName: string;
}

export function Conversation({ turns, typing, tutorName, studentName }: ConversationProps) {
  const firstQuestion = turns.findIndex((turn) => turn.move === "PRESENT");
  // The child's message shows at once, as sent; while the tutor prepares the answer, three dots (the owner,
  // 2026-10-12: "Đang gửi…" under the child's message read as the tutor thinking).
  const thinking = typing ?? (turns.some((turn) => turn.pending) ? { text: "" } : null);

  return (
    <section aria-label={`Trò chuyện với ${tutorName}`} className="flex flex-col gap-2.5">
      <ol role="log" aria-live="polite" className="flex flex-col gap-2.5">
        {turns.map((turn, index) => (
          <li key={turn.turn_id} className="motion-safe:animate-rise">
            {turn.move === "PRESENT" && index > firstQuestion && (
              <p className="my-1.5 flex items-center gap-3 text-sm text-slate-500" aria-hidden="true">
                <span className="h-px flex-1 bg-slate-200" />
                Câu tiếp theo
                <span className="h-px flex-1 bg-slate-200" />
              </p>
            )}
            {turn.kind && CARD_KINDS.has(turn.kind) ? (
              <TeachCard turn={turn} tutorName={tutorName} />
            ) : (
              <Bubble turn={turn} speaker={turn.actor === "tutor" ? tutorName : studentName} />
            )}
          </li>
        ))}
      </ol>
      {thinking && <TypingBubble text={thinking.text} tutorName={tutorName} />}
    </section>
  );
}

function Avatar({ label, tutor }: { label: string; tutor: boolean }) {
  if (tutor) {
    return (
      <span
        aria-hidden="true"
        className="flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white ring-1 ring-slate-200"
      >
        <Mascot size={32} />
      </span>
    );
  }
  return (
    <span
      aria-hidden="true"
      className="flex size-8 shrink-0 items-center justify-center rounded-full bg-gold-soft text-sm font-semibold text-gold-deep"
    >
      {label.charAt(0).toLocaleUpperCase("vi-VN")}
    </span>
  );
}

/** Memoized: while a turn streams in, the finished bubbles above it do not re-render. */
const Bubble = memo(function Bubble({ turn, speaker }: { turn: DisplayTurn; speaker: string }) {
  const tutor = turn.actor === "tutor";
  return (
    <div className={`flex items-end gap-2 ${tutor ? "" : "flex-row-reverse"}`}>
      <Avatar label={speaker} tutor={tutor} />
      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-base leading-relaxed md:text-[17px] ${
          tutor ? "rounded-bl-md bg-white ring-1 ring-slate-200" : "rounded-br-md bg-brand-700 text-white"
        }`}
      >
        {turn.kind === "RETELL_PROMPT" && (
          <p className="mb-1 inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-900">
            Con nói lại bằng lời của con
          </p>
        )}
        {tutor && turn.hint_level !== null && turn.hint_level > 0 && (
          <p className="mb-1 inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-900">
            <LightbulbIcon className="size-3.5" />
            Gợi ý mức {turn.hint_level}
          </p>
        )}
        <p className="whitespace-pre-wrap">
          <span className="sr-only">{speaker}: </span>
          <MathText text={turn.text} />
        </p>
      </div>
    </div>
  );
});

/** The tutor turn being streamed. Kept out of the live region: the final turn is announced once. */
function TypingBubble({ text, tutorName }: { text: string; tutorName: string }) {
  return (
    <div className="flex items-end gap-2" aria-hidden="true" data-testid="typing">
      <Avatar label={tutorName} tutor />
      <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-white px-3.5 py-2 text-base leading-relaxed ring-1 ring-slate-200 md:text-[17px]">
        {text ? (
          <p className="whitespace-pre-wrap">
            <MathText text={text} />
            <span className="ml-0.5 inline-block h-5 w-0.5 bg-slate-400 align-middle motion-safe:animate-pulse" />
          </p>
        ) : (
          <p className="flex gap-1.5 py-2">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                style={{ animationDelay: `${dot * 150}ms` }}
                className="size-2.5 rounded-full bg-brand-400 motion-safe:animate-bounce"
              />
            ))}
          </p>
        )}
      </div>
    </div>
  );
}

/** Messages of the teaching loop shown as cards rather than chat bubbles (chapter sessions). */
const CARD_KINDS = new Set(["NODE", "THEORY", "EXAMPLE", "PASS", "STOP", "SUMMARY"]);

const TeachCard = memo(function TeachCard({ turn, tutorName }: { turn: DisplayTurn; tutorName: string }) {
  const speaker = <span className="sr-only">{tutorName}: </span>;
  switch (turn.kind) {
    case "NODE":
      return (
        <p className="my-1 flex items-center gap-3 text-sm font-medium text-brand-900">
          <span aria-hidden="true" className="h-px flex-1 bg-brand-200" />
          <span className="max-w-[80%] text-center text-pretty">
            {speaker}
            <MathText text={turn.text} />
          </span>
          <span aria-hidden="true" className="h-px flex-1 bg-brand-200" />
        </p>
      );
    case "THEORY":
      return (
        <article className="rounded-2xl bg-white px-4 py-3 ring-1 ring-brand-200">
          <p className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-semibold tracking-wide text-brand-700 uppercase">
            <BookIcon className="size-4" />
            {tutorName} giảng bài
          </p>
          <p className="text-base leading-relaxed whitespace-pre-wrap md:text-[17px]">
            {speaker}
            <MathText text={turn.text} />
          </p>
        </article>
      );
    case "EXAMPLE":
      return <ExampleCard turn={turn} tutorName={tutorName} />;
    case "PASS":
      return (
        <article className="flex items-center gap-3 rounded-2xl bg-emerald-50 px-4 py-3 ring-1 ring-emerald-200">
          <StarIcon className="size-7 shrink-0 text-amber-500" />
          <p className="text-base font-semibold text-emerald-950 md:text-[17px]">
            {speaker}
            <MathText text={turn.text} />
          </p>
        </article>
      );
    case "STOP":
      return (
        <article className="rounded-2xl bg-amber-50 px-4 py-3 text-base text-amber-950 ring-1 ring-amber-200 md:text-[17px]">
          {speaker}
          <MathText text={turn.text} />
        </article>
      );
    default: // SUMMARY
      return (
        <article className="flex items-center gap-3 rounded-2xl bg-brand-700 px-4 py-3 text-white">
          <StarIcon className="size-7 shrink-0 text-amber-300" />
          <p className="text-base leading-relaxed font-medium md:text-[17px]">
            {speaker}
            <MathText text={turn.text} />
          </p>
        </article>
      );
  }
});

/** "Cô làm mẫu": the problem, the numbered steps, the answer (the text has one part per line). */
function ExampleCard({ turn, tutorName }: { turn: DisplayTurn; tutorName: string }) {
  const lines = turn.text.split("\n");
  const problem = lines.find((line) => line.startsWith("Bài:"));
  const steps = lines.filter((line) => /^Bước \d+:/.test(line));
  const answer = lines.find((line) => line.startsWith("Đáp số:"));
  return (
    <article className="rounded-2xl bg-white px-4 py-3 ring-1 ring-sky-200">
      <p className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-semibold tracking-wide text-sky-800 uppercase">
        <PencilIcon className="size-4" />
        {TEACH_KIND_LABEL.EXAMPLE}
      </p>
      <span className="sr-only">{tutorName}: </span>
      {problem && (
        <p className="text-base font-semibold md:text-[17px]">
          <MathText text={problem} />
        </p>
      )}
      <ol className="mt-2 flex flex-col gap-1.5">
        {steps.map((step, index) => (
          <li key={step} className="flex gap-2.5 text-base leading-relaxed md:text-[17px]">
            <span
              aria-hidden="true"
              className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-sky-100 text-sm font-semibold text-sky-900"
            >
              {index + 1}
            </span>
            <span>
              <span className="sr-only">Bước {index + 1}: </span>
              <MathText text={step.replace(/^Bước \d+:\s*/, "")} />
            </span>
          </li>
        ))}
      </ol>
      {answer && (
        <p className="mt-2 rounded-xl bg-emerald-50 px-3 py-1.5 text-base font-semibold text-emerald-950 md:text-[17px]">
          <MathText text={answer} />
        </p>
      )}
    </article>
  );
}
