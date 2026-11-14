import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";

import { useApi } from "../../api/apiContext";
import { useSubject } from "../subjects/subjectContext";

/**
 * The chapter a teacher's dashboard is about (``?chapter=``): tabs over the chapters of the library, kept
 * to the subject of the page (a chapter without a subject is math). English shows its unit even when it is
 * the only one, so the teacher always sees which unit the numbers are about.
 */
export function ChapterTabs({ current }: { current: string | undefined }) {
  const api = useApi();
  const subject = useSubject();
  const [params, setParams] = useSearchParams();
  const chapters = useQuery({
    queryKey: ["taught-chapters", subject.id],
    queryFn: () => api.getTaughtChapters!(),
    enabled: api.getTaughtChapters !== undefined,
    retry: false,
  });
  const mine = chapters.data?.filter((c) => (c.subject ?? "math") === subject.id);
  if (!mine || mine.length < (subject.id === "math" ? 2 : 1)) return null;
  const selected = current ?? mine[0]?.chapter_id;
  return (
    <nav aria-label={subject.id === "math" ? "Chương" : "Unit"} className="mb-4 flex flex-wrap gap-2">
      {mine.map((c) => (
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
