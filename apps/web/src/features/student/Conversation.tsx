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

  return (
    <section aria-label={`Trò chuyện với ${tutorName}`} className="flex flex-col gap-3">
      <ol role="log" aria-live="polite" className="flex flex-col gap-3">
        {turns.map((turn, index) => (
          <li key={turn.turn_id} className="motion-safe:animate-rise">
            {turn.move === "PRESENT" && index > firstQuestion && (
              <p className="my-2 flex items-center gap-3 text-base text-slate-500" aria-hidden="true">
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
      {typing && <TypingBubble text={typing.text} tutorName={tutorName} />}
    </section>
  );
}

function Avatar({ label, tutor }: { label: string; tutor: boolean }) {
  if (tutor) {
    return (
      <span
        aria-hidden="true"
        className="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white shadow-sm ring-1 ring-gold/40"
      >
        <Mascot size={38} />
      </span>
    );
  }
  return (
    <span
      aria-hidden="true"
      className="flex size-9 shrink-0 items-center justify-center rounded-full bg-gold-soft text-sm font-semibold text-gold-deep ring-1 ring-gold/40"
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
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-base leading-relaxed md:text-lg ${
          tutor
            ? "rounded-bl-md bg-white shadow-sm ring-1 ring-gold/30"
            : "rounded-br-md bg-brand-700 text-white"
        } ${turn.pending ? "opacity-60" : ""}`}
      >
        {turn.kind === "RETELL_PROMPT" && (
          <p className="mb-1 inline-flex items-center gap-1 rounded-full bg-sky-100 px-2.5 py-0.5 text-sm font-medium text-sky-900">
            Con nói lại bằng lời của con
          </p>
        )}
        {tutor && turn.hint_level !== null && turn.hint_level > 0 && (
          <p className="mb-1 inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-sm font-medium text-amber-900">
            <LightbulbIcon className="size-4" />
            Gợi ý mức {turn.hint_level}
          </p>
        )}
        <p className="whitespace-pre-wrap">
          <span className="sr-only">{speaker}: </span>
          <MathText text={turn.text} />
        </p>
        {turn.pending && <p className="mt-1 text-sm text-brand-100">Đang gửi…</p>}
      </div>
    </div>
  );
});

/** The tutor turn being streamed. Kept out of the live region: the final turn is announced once. */
function TypingBubble({ text, tutorName }: { text: string; tutorName: string }) {
  return (
    <div className="flex items-end gap-2" aria-hidden="true" data-testid="typing">
      <Avatar label={tutorName} tutor />
      <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-white px-4 py-2.5 text-base leading-relaxed shadow-sm ring-1 ring-gold/30 md:text-lg">
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
        <article className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-brand-200">
          <p className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-0.5 text-sm font-semibold text-brand-900">
            <BookIcon className="size-4" />
            {tutorName} giảng bài
          </p>
          <p className="text-base leading-relaxed whitespace-pre-wrap md:text-lg">
            {speaker}
            <MathText text={turn.text} />
          </p>
        </article>
      );
    case "EXAMPLE":
      return <ExampleCard turn={turn} tutorName={tutorName} />;
    case "PASS":
      return (
        <article className="flex items-center gap-3 rounded-2xl bg-emerald-50 p-4 ring-1 ring-emerald-300">
          <StarIcon className="size-8 shrink-0 text-amber-500" />
          <p className="text-lg font-semibold text-emerald-950">
            {speaker}
            <MathText text={turn.text} />
          </p>
        </article>
      );
    case "STOP":
      return (
        <article className="rounded-2xl bg-amber-50 p-4 text-base text-amber-950 ring-1 ring-amber-300 md:text-lg">
          {speaker}
          <MathText text={turn.text} />
        </article>
      );
    default: // SUMMARY
      return (
        <article className="flex items-center gap-3 rounded-2xl bg-brand-700 p-4 text-white">
          <StarIcon className="size-8 shrink-0 text-amber-300" />
          <p className="text-base leading-relaxed font-medium md:text-lg">
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
    <article className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-sky-200">
      <p className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-sky-50 px-2.5 py-0.5 text-sm font-semibold text-sky-900">
        <PencilIcon className="size-4" />
        {TEACH_KIND_LABEL.EXAMPLE}
      </p>
      <span className="sr-only">{tutorName}: </span>
      {problem && (
        <p className="text-base font-semibold md:text-lg">
          <MathText text={problem} />
        </p>
      )}
      <ol className="mt-2 flex flex-col gap-1.5">
        {steps.map((step, index) => (
          <li key={step} className="flex gap-2.5 text-base leading-relaxed md:text-lg">
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
        <p className="mt-2 rounded-xl bg-emerald-50 px-3 py-1.5 text-base font-semibold text-emerald-950 md:text-lg">
          <MathText text={answer} />
        </p>
      )}
    </article>
  );
}
