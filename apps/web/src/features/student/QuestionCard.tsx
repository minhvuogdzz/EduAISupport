import type { CurrentItem } from "../../api/contract";
import { MathText } from "../../components/MathText";

export function QuestionCard({ item, total, label }: { item: CurrentItem; total: number; label?: string }) {
  return (
    <section
      aria-labelledby="question-title"
      className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200 md:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="question-title" className="text-lg font-semibold text-teal-800">
          {label ?? `Câu ${item.position}/${total}`}
        </h2>
        {item.expecting === "EXPLANATION" && (
          <span className="rounded-full bg-sky-100 px-3 py-1 text-base text-sky-900">
            Cô muốn nghe con giải thích
          </span>
        )}
      </div>
      <p className="mt-3 text-2xl leading-snug font-medium text-pretty md:text-3xl">
        <MathText text={item.stem} blanks />
      </p>
    </section>
  );
}
