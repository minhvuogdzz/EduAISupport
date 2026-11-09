import type { CSSProperties } from "react";

import "./burst.css";

const COLOURS = ["#f97316", "#facc15", "#22c55e", "#38bdf8", "#a855f7", "#ec4899"];
const PIECES = Array.from({ length: 16 }, (_, i) => {
  const angle = (i / 16) * Math.PI * 2;
  const reach = 62 + (i % 3) * 22;
  return {
    "--x": `${Math.round(Math.cos(angle) * reach)}px`,
    "--y": `${Math.round(Math.sin(angle) * reach)}px`,
    "--turn": `${(i % 5) * 80 + 90}deg`,
    "--c": COLOURS[i % COLOURS.length],
  } as CSSProperties;
});

/** A little confetti pop. Each new value of `fire` plays it once; 0 shows nothing. */
export function Burst({ fire }: { fire: number }) {
  if (fire === 0) return null;
  return (
    <span className="burst" key={fire} aria-hidden="true">
      {PIECES.map((style, index) => (
        <i key={index} style={style} />
      ))}
    </span>
  );
}
