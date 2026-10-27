import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useApi } from "../api/apiContext";
import type { FigureView } from "../api/contract";

/** FIG-1: the pictures of one chapter's questions, found by the "[Hình: …]" their words hold. */
interface FiguresValue {
  byTag: Map<string, FigureView>;
  byQuestion: Map<string, FigureView[]>;
  who: "student" | "teacher";
}

const FiguresContext = createContext<FiguresValue | null>(null);

const TAG = /\[Hình\b[^\]]*\]/g;

/** One line, spaces collapsed: how the API keeps a tag. */
export function tagKey(tag: string): string {
  return tag.replace(/\s+/g, " ").trim();
}

/**
 * The figures of a chapter around its screens. Without a real API, or while they load, nothing changes:
 * the words keep their "[Hình: …]" description.
 */
export function FiguresProvider({
  chapterId,
  who,
  children,
}: {
  chapterId: string | undefined;
  who: "student" | "teacher";
  children: ReactNode;
}) {
  const api = useApi();
  const list = useQuery({
    queryKey: ["figures", who, chapterId],
    queryFn: () => api.figures!.list(chapterId!, who),
    enabled: Boolean(api.figures && chapterId),
    staleTime: 60_000,
  });
  const value = useMemo<FiguresValue>(() => {
    const byTag = new Map<string, FigureView>();
    const byQuestion = new Map<string, FigureView[]>();
    for (const figure of list.data ?? []) {
      byTag.set(tagKey(figure.tag), figure);
      byQuestion.set(figure.question_id, [...(byQuestion.get(figure.question_id) ?? []), figure]);
    }
    return { byTag, byQuestion, who };
  }, [list.data, who]);
  return <FiguresContext value={value}>{children}</FiguresContext>;
}

export function useFigures(): FiguresValue | null {
  return useContext(FiguresContext);
}

/** The text without the descriptions that have a picture, and those pictures in the order of the text. */
export function pullFigures(
  text: string,
  figures: FiguresValue | null,
): { text: string; found: FigureView[] } {
  if (!figures || !text.includes("[Hình")) return { text, found: [] };
  const found: FigureView[] = [];
  const rest = text.replace(TAG, (tag) => {
    const figure = figures.byTag.get(tagKey(tag));
    if (!figure) return tag;
    found.push(figure);
    return "";
  });
  return found.length
    ? {
        text: rest
          .replace(/[ \t]+\n/g, "\n")
          .replace(/ {2,}/g, " ")
          .trim(),
        found,
      }
    : { text, found };
}

/** The pictures of an item whose words do not hold the description (a sub-question of a figure). */
export function questionFigures(figures: FiguresValue | null, itemId: string, stem: string): FigureView[] {
  if (!figures || !itemId || pullFigures(stem, figures).found.length) return [];
  return figures.byQuestion.get(itemId.replace(/([0-9])[a-e]$/, "$1")) ?? [];
}

/**
 * One picture, fetched when it comes near the screen. Big and clear, never wider than its card; the
 * description is its alternative text.
 */
export function FigureImage({ figure }: { figure: FigureView }) {
  const api = useApi();
  const figures = useFigures();
  const box = useRef<HTMLSpanElement>(null);
  const [near, setNear] = useState(typeof IntersectionObserver === "undefined");
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    const node = box.current;
    if (near || !node) return;
    const watcher = new IntersectionObserver(
      (entries) => entries.some((entry) => entry.isIntersecting) && setNear(true),
      { rootMargin: "400px" },
    );
    watcher.observe(node);
    return () => watcher.disconnect();
  }, [near]);

  useEffect(() => {
    if (!near || !api.figures) return;
    let revoked = false;
    let made: string | null = null;
    void api.figures
      .image(figure.figure_id, figure.version, figures?.who ?? "student")
      .then((blob) => {
        if (revoked) return;
        made = URL.createObjectURL(blob);
        setUrl(made);
      })
      .catch(() => undefined);
    return () => {
      revoked = true;
      if (made) URL.revokeObjectURL(made);
    };
  }, [near, api, figure.figure_id, figure.version, figures?.who]);

  return (
    <span ref={box} role="figure" aria-label={figure.alt} className="my-2 block">
      {url ? (
        <img
          src={url}
          alt={figure.alt}
          width={figure.width}
          height={figure.height}
          className="mx-auto h-auto max-h-[22rem] w-auto max-w-full rounded-xl bg-white ring-1 ring-slate-200"
        />
      ) : (
        <span
          aria-hidden="true"
          style={{ aspectRatio: `${figure.width} / ${figure.height}` }}
          className="mx-auto block max-h-[22rem] w-full max-w-md animate-pulse rounded-xl bg-slate-100"
        />
      )}
    </span>
  );
}
