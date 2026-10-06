/**
 * CAVAT's mascot: a white egret ("cò", the bird of Vietnamese rice fields and lullabies) with a
 * turquoise scarf. Drawn here, not taken from anywhere. Each mood matches a moment of the lesson.
 */
export type Mood = "happy" | "listening" | "thinking" | "encouraging" | "celebrating";

const MOOD_LABEL: Record<Mood, string> = {
  happy: "vui vẻ",
  listening: "đang lắng nghe",
  thinking: "đang suy nghĩ",
  encouraging: "cổ vũ",
  celebrating: "ăn mừng",
};

interface MascotProps {
  mood?: Mood;
  size?: number;
  className?: string;
  /** Decorative by default; pass a label when the mascot says something on its own. */
  label?: string;
}

const INK = "var(--color-ink)";

export function Mascot({ mood = "happy", size = 96, className, label }: MascotProps) {
  const closed = mood === "happy" || mood === "celebrating" || mood === "encouraging";
  const wingUp = mood === "celebrating";
  return (
    <svg
      viewBox="0 0 120 120"
      width={size}
      height={size}
      className={className}
      role={label ? "img" : undefined}
      aria-label={label ? `${label} (${MOOD_LABEL[mood]})` : undefined}
      aria-hidden={label ? undefined : true}
    >
      <circle cx="58" cy="64" r="50" fill="var(--color-gold-soft)" opacity="0.75" />
      {mood === "celebrating" && (
        <g>
          <circle cx="16" cy="26" r="3.5" fill="var(--color-gold)" />
          <circle cx="102" cy="14" r="3" fill="var(--color-brand-400)" />
          <rect
            x="22"
            y="44"
            width="6"
            height="3"
            rx="1.5"
            fill="var(--color-leaf)"
            transform="rotate(-30 25 45)"
          />
          <rect x="98" y="58" width="6" height="3" rx="1.5" fill="#fb7185" transform="rotate(25 101 59)" />
          <circle cx="40" cy="12" r="2.5" fill="#fb7185" />
        </g>
      )}
      {mood === "thinking" && (
        <g fill="white" stroke="var(--color-brand-200)" strokeWidth="1.5">
          <circle cx="44" cy="22" r="3" />
          <circle cx="36" cy="13" r="4.5" />
          <ellipse cx="22" cy="6" rx="9" ry="5.5" />
        </g>
      )}
      {mood === "encouraging" && (
        <path
          d="M100 30c0-3.5 4.5-4.5 5.5-1 1-3.5 5.5-2.5 5.5 1 0 3-5.5 6.5-5.5 6.5S100 33 100 30z"
          fill="#fb7185"
        />
      )}
      {/* legs */}
      <g stroke="var(--color-gold-deep)" strokeWidth="3" strokeLinecap="round">
        <path d="M50 92 L48 109 M64 92 L66 109" />
        <path d="M42 109 H54 M60 109 H72" />
      </g>
      {/* tail and body */}
      <path
        d="M30 70 q-13 -3 -18 6 q11 3 20 2 z"
        fill="white"
        stroke="var(--color-brand-200)"
        strokeWidth="2"
      />
      <ellipse cx="57" cy="76" rx="30" ry="21" fill="white" stroke="var(--color-brand-200)" strokeWidth="2" />
      {/* wing */}
      {wingUp ? (
        <path
          d="M46 70 q-6 -26 14 -36 q2 18 10 30 q-12 10 -24 6 z"
          fill="var(--color-gold-soft)"
          stroke="var(--color-gold)"
          strokeWidth="1.5"
        />
      ) : (
        <path
          d="M40 74 q14 -12 32 -2 q-6 14 -20 14 q-9 -2 -12 -12 z"
          fill="var(--color-gold-soft)"
          stroke="var(--color-gold)"
          strokeWidth="1.5"
        />
      )}
      {/* neck and head */}
      <path d="M70 66 q8 -14 4 -30" stroke="white" strokeWidth="13" strokeLinecap="round" fill="none" />
      <path d="M64 64 q8 -12 4 -28" stroke="var(--color-brand-200)" strokeWidth="2" fill="none" />
      <circle cx="76" cy="30" r="14" fill="white" stroke="var(--color-brand-200)" strokeWidth="2" />
      <path d="M69 17 q-3 -9 6 -11 q-2 6 2 10 z" fill="var(--color-brand-400)" />
      {/* scarf */}
      <path d="M64 48 q11 7 21 0 l-1.5 7 q-9 5 -18 0 z" fill="var(--color-brand-500)" />
      <path d="M80 52 l7 12 l-6 -1 z" fill="var(--color-brand-600)" />
      {/* beak */}
      <path
        d="M88 28 L111 33 L88 36.5 z"
        fill="var(--color-gold)"
        stroke="var(--color-gold-deep)"
        strokeWidth="1"
      />
      {/* eye and cheek */}
      {closed ? (
        <path d="M73 29 q3.5 -4 7 0" stroke={INK} strokeWidth="2.4" strokeLinecap="round" fill="none" />
      ) : (
        <circle cx="77" cy={mood === "thinking" ? 26.5 : 28.5} r="2.6" fill={INK} />
      )}
      <circle cx="82" cy="37" r="3" fill="#fda4af" opacity="0.6" />
      {mood === "listening" && (
        <g stroke="var(--color-brand-500)" strokeWidth="2" strokeLinecap="round" fill="none">
          <path d="M94 18 q4 4 0 8" />
          <path d="M99 14 q7 8 0 16" />
        </g>
      )}
    </svg>
  );
}
