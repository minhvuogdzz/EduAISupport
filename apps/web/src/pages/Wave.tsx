/** A soft wave between two coloured bands; `flip` draws it for the bottom edge of a band. */
export function Wave({ colour, flip = false }: { colour: string; flip?: boolean }) {
  return (
    <svg
      className={`hm-wave ${flip ? "is-flipped" : ""}`}
      viewBox="0 0 1440 64"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d="M0 34C200 74 420 2 720 26s520 42 720 4v34H0z" fill={colour} />
    </svg>
  );
}
