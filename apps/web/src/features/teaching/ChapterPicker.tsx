import { useSearchParams } from "react-router";

import type { ChapterRef } from "../../api/contract";

/**
 * Which chapter a student or a parent looks at (REFORM 4.4): one button per chapter the tutor teaches,
 * drawn only when there is a choice. The pick lives in the page's `?chapter=`, so a reload and a link keep
 * it; without it the server answers with its first chapter (`current`, the chapter of the data on screen).
 */
export function ChapterPicker({ chapters, current }: { chapters: ChapterRef[]; current: string }) {
  const [params, setParams] = useSearchParams();
  if (chapters.length < 2) return null;
  const selected = params.get("chapter") ?? current;
  return (
    <nav aria-label="Chọn chương" className="mt-4 flex flex-wrap gap-2">
      {chapters.map((c) => (
        <button
          key={c.chapter_id}
          type="button"
          aria-pressed={c.chapter_id === selected}
          onClick={() => {
            const next = new URLSearchParams(params);
            next.set("chapter", c.chapter_id);
            setParams(next, { replace: true });
          }}
          className={`min-h-11 rounded-full px-5 text-base font-semibold ${
            c.chapter_id === selected
              ? "bg-brand-700 text-white"
              : "bg-white text-brand-900 ring-1 ring-brand-200 hover:bg-brand-50"
          }`}
        >
          {c.title}
        </button>
      ))}
    </nav>
  );
}
