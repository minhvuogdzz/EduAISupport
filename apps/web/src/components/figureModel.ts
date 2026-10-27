import { createContext, useContext } from "react";
import type { FigureView } from "../api/contract";

export interface FiguresValue {
  byTag: Map<string, FigureView[]>;
  byQuestion: Map<string, FigureView[]>;
  who: "student" | "teacher";
}

export const FiguresContext = createContext<FiguresValue | null>(null);
const TAG = /\[Hình\b[^\]]*\]/g;

export function tagKey(tag: string): string {
  return tag.replace(/\s+/g, " ").trim();
}

export function questionKey(itemId: string): string {
  return itemId.replace(/([0-9])[a-z]$/i, "$1");
}

export function useFigures(): FiguresValue | null {
  return useContext(FiguresContext);
}

/** Only use an unambiguous tag, or the drawing bound to this exact question. */
export function pullFigures(
  text: string,
  figures: FiguresValue | null,
  questionId?: string,
): { text: string; found: FigureView[] } {
  if (!figures || !text.includes("[Hình")) return { text, found: [] };
  const found: FigureView[] = [];
  const rest = text.replace(TAG, (tag) => {
    const candidates = questionId
      ? (figures.byQuestion.get(questionKey(questionId)) ?? []).filter((f) => tagKey(f.tag) === tagKey(tag))
      : (figures.byTag.get(tagKey(tag)) ?? []);
    const figure = candidates.length === 1 ? candidates[0] : undefined;
    if (!figure) return tag;
    if (!found.some((f) => f.figure_id === figure.figure_id)) found.push(figure);
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

/** Pictures attached to a sub-question without repeating ones already embedded in its stem. */
export function questionFigures(figures: FiguresValue | null, itemId: string, stem: string): FigureView[] {
  if (!figures || !itemId) return [];
  const embedded = new Set(pullFigures(stem, figures, itemId).found.map((f) => f.figure_id));
  return (figures.byQuestion.get(questionKey(itemId)) ?? []).filter((f) => !embedded.has(f.figure_id));
}
