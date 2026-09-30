import { useCallback, useEffect, useRef } from "react";

const NEAR_BOTTOM_PX = 48;

/**
 * Keeps a chat scroller at its newest message: on new content, and when the scroller resizes while
 * the student was at the bottom (on-screen keyboard opening on a tablet, rotation, fonts loading).
 * Returns the callback ref to put on the scrolling element.
 */
export function useStickToBottom(contentKey: unknown) {
  const scroller = useRef<HTMLElement | null>(null);
  const pinned = useRef(true);

  const ref = useCallback((node: HTMLElement | null) => {
    scroller.current = node;
    if (!node) return;
    const toBottom = () => {
      node.scrollTop = node.scrollHeight;
    };
    const onScroll = () => {
      pinned.current = node.scrollHeight - node.scrollTop - node.clientHeight < NEAR_BOTTOM_PX;
    };
    node.addEventListener("scroll", onScroll, { passive: true });
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(() => {
            if (pinned.current) toBottom();
          });
    observer?.observe(node);
    if (node.firstElementChild) observer?.observe(node.firstElementChild);
    toBottom();
    return () => {
      node.removeEventListener("scroll", onScroll);
      observer?.disconnect();
    };
  }, []);

  // A new turn or streamed word: the student is waiting for it, so always show it.
  useEffect(() => {
    const node = scroller.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
    pinned.current = true;
  }, [contentKey]);

  return ref;
}
