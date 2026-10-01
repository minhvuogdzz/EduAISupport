import { memo } from "react";

import { LightbulbIcon } from "../../components/icons";
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
          <li key={turn.turn_id}>
            {turn.move === "PRESENT" && index > firstQuestion && (
              <p className="my-2 flex items-center gap-3 text-base text-slate-500" aria-hidden="true">
                <span className="h-px flex-1 bg-slate-200" />
                Câu tiếp theo
                <span className="h-px flex-1 bg-slate-200" />
              </p>
            )}
            <Bubble turn={turn} speaker={turn.actor === "tutor" ? tutorName : studentName} />
          </li>
        ))}
      </ol>
      {typing && <TypingBubble text={typing.text} tutorName={tutorName} />}
    </section>
  );
}

function Avatar({ label, tutor }: { label: string; tutor: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`flex size-11 shrink-0 items-center justify-center rounded-full text-base font-semibold ${
        tutor ? "bg-teal-700 text-white" : "bg-sky-200 text-sky-950"
      }`}
    >
      {tutor ? label : label.charAt(0).toLocaleUpperCase("vi-VN")}
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
        className={`max-w-[85%] rounded-3xl px-4 py-3 text-xl leading-relaxed ${
          tutor ? "rounded-bl-md bg-white ring-1 ring-slate-200" : "rounded-br-md bg-sky-100 text-sky-950"
        } ${turn.pending ? "opacity-60" : ""}`}
      >
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
        {turn.pending && <p className="mt-1 text-sm text-sky-800">Đang gửi…</p>}
      </div>
    </div>
  );
});

/** The tutor turn being streamed. Kept out of the live region: the final turn is announced once. */
function TypingBubble({ text, tutorName }: { text: string; tutorName: string }) {
  return (
    <div className="flex items-end gap-2" aria-hidden="true" data-testid="typing">
      <Avatar label={tutorName} tutor />
      <div className="max-w-[85%] rounded-3xl rounded-bl-md bg-white px-4 py-3 text-xl leading-relaxed ring-1 ring-slate-200">
        {text ? (
          <p className="whitespace-pre-wrap">
            <MathText text={text} />
            <span className="ml-0.5 inline-block h-5 w-0.5 bg-slate-400 align-middle motion-safe:animate-pulse" />
          </p>
        ) : (
          <p className="flex gap-1.5 py-2">
            {[0, 1, 2].map((dot) => (
              <span key={dot} className="size-2.5 rounded-full bg-slate-400 motion-safe:animate-bounce" />
            ))}
          </p>
        )}
      </div>
    </div>
  );
}
