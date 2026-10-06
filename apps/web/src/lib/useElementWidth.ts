import { useCallback, useState } from "react";

/**
 * The rendered width of an element, kept up to date. Charts draw at their real pixel size with it, so
 * labels keep their font size on a phone and on a wide screen (no viewBox stretching).
 */
export function useElementWidth(fallback: number): [(node: HTMLElement | null) => void, number] {
  const [width, setWidth] = useState(fallback);
  const ref = useCallback((node: HTMLElement | null) => {
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry && entry.contentRect.width > 0) setWidth(Math.round(entry.contentRect.width));
    });
    observer.observe(node);
  }, []);
  return [ref, width];
}
