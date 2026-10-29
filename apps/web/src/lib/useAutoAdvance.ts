import { useEffect, useRef, useState } from "react";

/** Rotation stops off-screen, in a hidden tab and with reduced motion. */
export function useAutoAdvance(count: number, delay = 2000) {
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [visible, setVisible] = useState(true);
  const [hidden, setHidden] = useState(false);
  const [reduced, setReduced] = useState(false);
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const media = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const updateMedia = () => setReduced(media?.matches ?? false);
    const updateHidden = () => setHidden(document.hidden);
    updateMedia();
    updateHidden();
    media?.addEventListener?.("change", updateMedia);
    document.addEventListener("visibilitychange", updateHidden);
    const observer = window.IntersectionObserver
      ? new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.15 })
      : null;
    if (ref.current) observer?.observe(ref.current);
    return () => {
      media?.removeEventListener?.("change", updateMedia);
      document.removeEventListener("visibilitychange", updateHidden);
      observer?.disconnect();
    };
  }, []);
  const running = playing && visible && !hidden && !reduced;
  useEffect(() => {
    if (!running) return;
    const timer = window.setTimeout(() => setSelected((selected + 1) % count), delay);
    return () => window.clearTimeout(timer);
  }, [running, selected, count, delay]);
  return {
    ref,
    selected,
    setSelected,
    playing,
    setPlaying,
    running,
    reduced,
  };
}
