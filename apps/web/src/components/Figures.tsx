import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useApi } from "../api/apiContext";
import type { FigureView } from "../api/contract";
import { FiguresContext, tagKey, useFigures, type FiguresValue } from "./figureModel";

/** Keep descriptions intact while loading, or in the offline mock with no figures API. */
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
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  const value = useMemo<FiguresValue>(() => {
    const byTag = new Map<string, FigureView[]>();
    const byQuestion = new Map<string, FigureView[]>();
    for (const f of list.data ?? []) {
      if (f.tag) byTag.set(tagKey(f.tag), [...(byTag.get(tagKey(f.tag)) ?? []), f]);
      byQuestion.set(f.question_id, [...(byQuestion.get(f.question_id) ?? []), f]);
    }
    return { byTag, byQuestion, who };
  }, [list.data, who]);
  return <FiguresContext value={value}>{children}</FiguresContext>;
}

/** Authenticated bytes are rendered through a private object URL, never a public image URL. */
export function FigureImage({ figure }: { figure: FigureView }) {
  const api = useApi();
  const figures = useFigures();
  const box = useRef<HTMLSpanElement>(null);
  const [near, setNear] = useState(typeof IntersectionObserver === "undefined");
  const [attempt, setAttempt] = useState(0);
  const who = figures?.who ?? "student";
  const key = `${who}:${figure.figure_id}:${figure.version}:${attempt}`;
  const [loaded, setLoaded] = useState<{ key: string; url: string | null } | null>(null);
  const url = loaded?.key === key ? loaded.url : null;
  const failed = loaded?.key === key && !loaded.url;

  useEffect(() => {
    const node = box.current;
    if (near || !node) return;
    const watcher = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setNear(true);
      },
      { rootMargin: "400px" },
    );
    watcher.observe(node);
    return () => watcher.disconnect();
  }, [near]);

  useEffect(() => {
    if (!near || !api.figures) return;
    let cancelled = false;
    let made: string | null = null;
    void api.figures
      .image(figure.figure_id, figure.version, who)
      .then((blob) => {
        if (cancelled) return;
        made = URL.createObjectURL(blob);
        setLoaded({ key, url: made });
      })
      .catch(() => {
        if (!cancelled) setLoaded({ key, url: null });
      });
    return () => {
      cancelled = true;
      if (made) URL.revokeObjectURL(made);
    };
  }, [near, api, figure.figure_id, figure.version, who, key]);

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
      ) : failed ? (
        <span className="block rounded-xl bg-amber-50 p-3 text-sm text-amber-950">
          Chưa tải được hình. {figure.alt}
          <button type="button" onClick={() => setAttempt((n) => n + 1)} className="ml-2 underline">
            Tải lại hình
          </button>
        </span>
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
