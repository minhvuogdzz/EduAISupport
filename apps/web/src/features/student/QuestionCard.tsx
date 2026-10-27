import type { CurrentItem } from "../../api/contract";
import { FigureImage, questionFigures, useFigures } from "../../components/Figures";
import { MathText } from "../../components/MathText";

export function QuestionCard({ item, total, label }: { item: CurrentItem; total: number; label?: string }) {
  const extra = questionFigures(useFigures(), item.item_id, item.stem);
  return (
    <section
      aria-labelledby="question-title"
      className="rounded-2xl bg-white px-4 py-3 shadow-sm ring-1 ring-slate-200"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="question-title" className="text-xs font-semibold tracking-wide text-brand-700 uppercase">
          {label ?? `Câu ${item.position}/${total}`}
        </h2>
        {item.expecting === "EXPLANATION" && (
          <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs text-sky-900 ring-1 ring-sky-200">
            Cô muốn nghe con giải thích
          </span>
        )}
      </div>
      {extra.map((figure) => (
        <FigureImage key={figure.figure_id} figure={figure} />
      ))}
      <p className="mt-1 text-[17px] leading-snug font-medium text-pretty md:text-lg">
        <MathText text={item.stem} blanks />
      </p>
    </section>
  );
}
