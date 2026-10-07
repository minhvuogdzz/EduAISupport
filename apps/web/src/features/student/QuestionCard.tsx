import type { CurrentItem } from "../../api/contract";
import { MathText } from "../../components/MathText";

export function QuestionCard({ item, total, label }: { item: CurrentItem; total: number; label?: string }) {
  return (
    <section
      aria-labelledby="question-title"
      className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="question-title" className="text-sm font-semibold text-brand-800">
          {label ?? `Câu ${item.position}/${total}`}
        </h2>
        {item.expecting === "EXPLANATION" && (
          <span className="rounded-full bg-sky-100 px-2.5 py-0.5 text-sm text-sky-900">
            Cô muốn nghe con giải thích
          </span>
        )}
      </div>
      <p className="mt-1.5 text-lg leading-snug font-medium text-pretty md:text-xl">
        <MathText text={item.stem} blanks />
      </p>
    </section>
  );
}
