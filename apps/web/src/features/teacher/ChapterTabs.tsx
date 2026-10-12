import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";

import { useApi } from "../../api/apiContext";

/** The chapter a teacher's dashboard is about (``?chapter=``): tabs over the chapters of the library. */
export function ChapterTabs({ current }: { current: string | undefined }) {
  const api = useApi();
  const [params, setParams] = useSearchParams();
  const chapters = useQuery({
    queryKey: ["library-chapters"],
    queryFn: () => api.library!.chapters(),
    enabled: api.library !== undefined,
    retry: false,
  });
  if (!chapters.data || chapters.data.length < 2) return null;
  const selected = current ?? chapters.data[0]?.chapter_id;
  return (
    <nav aria-label="Chương" className="mb-4 flex flex-wrap gap-2">
      {chapters.data.map((c) => (
        <button
          key={c.chapter_id}
          type="button"
          aria-pressed={c.chapter_id === selected}
          onClick={() => {
            const next = new URLSearchParams(params);
            next.set("chapter", c.chapter_id);
            next.delete("node");
            setParams(next, { replace: true });
          }}
          className={
            c.chapter_id === selected
              ? "rounded-full bg-brand-700 px-4 py-1.5 text-sm font-semibold text-white"
              : "rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-300"
          }
        >
          {c.title}
        </button>
      ))}
    </nav>
  );
}
