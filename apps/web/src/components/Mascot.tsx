import { useId } from "react";

/** Monkey Buddy: the same character, with a distinct pose and expression for each learning moment. */
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
  label?: string;
  animated?: boolean;
  activity?: "writing";
}
export function Mascot({
  mood = "happy",
  size = 96,
  className = "",
  label,
  animated = false,
  activity,
}: MascotProps) {
  const id = useId();
  const fur = `${id}-fur`;
  const face = `${id}-face`;
  const coat = `${id}-coat`;
  const writing = activity === "writing";
  const celebrating = mood === "celebrating";
  const thinking = mood === "thinking";
  const listening = mood === "listening";
  const encouraging = mood === "encouraging";
  return (
    <svg
      viewBox="0 0 200 220"
      width={size}
      height={size}
      className={`monkey-buddy ${writing ? "buddy-writing" : ""} buddy-${mood} ${animated ? "buddy-alive" : ""} ${size < 64 ? "buddy-compact" : ""} ${className}`}
      role={label ? "img" : undefined}
      aria-label={label ? `${label} (${MOOD_LABEL[mood]})` : undefined}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <defs>
        <linearGradient id={fur} x1="0" y1="0" x2="0.8" y2="1">
          <stop stopColor="#bd8051" />
          <stop offset="1" stopColor="#805037" />
        </linearGradient>
        <radialGradient id={face} cx="40%" cy="30%" r="75%">
          <stop stopColor="#fff0cd" />
          <stop offset="1" stopColor="#edc38e" />
        </radialGradient>
        <linearGradient id={coat} x2="0.8" y2="1">
          <stop stopColor="#82b0d0" />
          <stop offset="1" stopColor="#315f86" />
        </linearGradient>
      </defs>
      <ellipse className="buddy-shadow" cx="100" cy="211" rx="48" ry="5" fill="#315f86" opacity=".12" />
      <g stroke="#573d2d" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path
          className="buddy-tail"
          d="M139 182c48 22 57-36 34-39-17-2-20 19-7 20"
          fill="none"
          stroke="#9c6642"
          strokeWidth="10"
        />
        <g className="buddy-body">
          <ellipse cx="74" cy="203" rx="18" ry="9" fill={`url(#${fur})`} />
          <ellipse cx="126" cy="203" rx="18" ry="9" fill={`url(#${fur})`} />
          <path d="m65 203 9-1m47 1 9-1" stroke="#edc38e" />
          <path d="M61 152c4-18 74-18 78 0l-2 33c-2 23-72 23-74 0Z" fill={`url(#${coat})`} stroke="#315f86" />
          <path d="M85 154q15 12 30 0" fill="none" stroke="#c9e0f0" />
          <path d="M81 182q19 12 38 0v9q-19 8-38 0Z" fill="#315f86" stroke="none" opacity=".5" />
          <circle cx="100" cy="171" r="9" fill="#efd79b" stroke="none" />
          <path d="m95 174 2-6 3 4 3-4 2 6" fill="none" stroke="#315f86" strokeWidth="1.8" />
        </g>
        <g className="buddy-arm-left" style={writing ? { opacity: 0 } : undefined}>
          <path
            d={celebrating ? "M64 158 44 142 36 123" : "M64 157q-16 6-17 23"}
            fill="none"
            stroke="#6099c5"
            strokeWidth="17"
          />
          <ellipse
            cx={celebrating ? 34 : 47}
            cy={celebrating ? 117 : 183}
            rx="9"
            ry="11"
            fill={`url(#${face})`}
            transform={celebrating ? "rotate(-25 34 117)" : undefined}
          />
          {celebrating && (
            <path d="m28 112-4-7m10 4-1-9m7 10 3-7" fill="none" stroke="#edc38e" strokeWidth="5" />
          )}
        </g>
        {writing && (
          <g className="buddy-writing-arm">
            <path d="M65 158Q38 157 27 131" fill="none" stroke="#6099c5" strokeWidth="17" />
            <g className="buddy-writing-hand">
              <path d="m-5 83 36 51" fill="none" stroke="#9b7337" strokeWidth="9" />
              <path d="m-5 83 36 51" fill="none" stroke="#e9c16c" strokeWidth="6" />
              <path d="m-10 76 2 12 6-4Z" fill="#ead5a3" stroke="none" />
              <path d="m-10 76 1 5 3-2Z" fill="#384c35" stroke="none" />
              <ellipse
                cx="26"
                cy="132"
                rx="10"
                ry="12"
                fill={`url(#${face})`}
                transform="rotate(-30 26 132)"
              />
              <path d="m22 126 8 7m-10-1 8 7" fill="none" stroke="#c79b6c" strokeWidth="1.5" />
            </g>
          </g>
        )}
        <g className="buddy-head" key={mood}>
          <circle cx="40" cy="85" r="22" fill={`url(#${fur})`} />
          <circle cx="160" cy="85" r="22" fill={`url(#${fur})`} />
          <circle cx="40" cy="85" r="12" fill="#e5ad84" stroke="none" />
          <circle cx="160" cy="85" r="12" fill="#e5ad84" stroke="none" />
          <path
            d="M43 83C39 22 80 22 99 30c31-16 63 12 59 54 4 39-21 61-58 61S39 125 43 83Z"
            fill={`url(#${fur})`}
          />
          <path d="M89 31q-8-16 5-17-2 9 8 14 1-17 13-14-8 7-4 16" fill={`url(#${fur})`} />
          <path
            d="M100 59C72 30 47 62 60 87c-15 37 7 50 40 50s55-13 40-50c13-25-12-57-40-28Z"
            fill={`url(#${face})`}
            stroke="none"
          />
          <path d="M56 63q7-22 25-18" fill="none" stroke="#d9aa76" strokeWidth="3" opacity=".65" />
          <g className="buddy-brows" fill="none" strokeWidth="3">
            <path
              d={
                thinking
                  ? "m72 65 15 3m25-5 15-4"
                  : listening
                    ? "M72 62q7-5 15-1m26 0q8-4 15 1"
                    : "M73 65q7-4 14-1m26 0q7-3 14 1"
              }
            />
          </g>
          {celebrating ? (
            <path d="M71 83q9-13 18 0m22 0q9-13 18 0" fill="none" strokeWidth="4" />
          ) : (
            <g className="buddy-eyes">
              <ellipse cx="81" cy="82" rx="10" ry="13" fill="#fffdf4" stroke="none" />
              <g className={thinking ? "buddy-gaze" : undefined}>
                <ellipse
                  cx={thinking ? 85 : 83}
                  cy={thinking ? 79 : 83}
                  rx="5.8"
                  ry="8.5"
                  fill="#382c24"
                  stroke="none"
                />
                <circle cx={thinking ? 86 : 84} cy={thinking ? 76 : 80} r="2.4" fill="white" stroke="none" />
              </g>
              {encouraging ? (
                <path d="m111 84 8-5 9 4" fill="none" strokeWidth="3.5" />
              ) : (
                <>
                  <ellipse cx="119" cy="82" rx="10" ry="13" fill="#fffdf4" stroke="none" />
                  <ellipse
                    cx={thinking ? 123 : 117}
                    cy={thinking ? 79 : 83}
                    rx="5.8"
                    ry="8.5"
                    fill="#382c24"
                    stroke="none"
                  />
                  <circle
                    cx={thinking ? 124 : 118}
                    cy={thinking ? 76 : 80}
                    r="2.4"
                    fill="white"
                    stroke="none"
                  />
                </>
              )}
            </g>
          )}
          <ellipse cx="66" cy="102" rx="10" ry="6" fill="#dc9378" stroke="none" opacity=".65" />
          <ellipse cx="134" cy="102" rx="10" ry="6" fill="#dc9378" stroke="none" opacity=".65" />
          <path d="M96 97q4 4 8 0" fill="none" strokeWidth="3" />
          {thinking ? (
            <path d="M95 115q7-5 13-1" fill="none" />
          ) : celebrating ? (
            <g>
              <path d="M85 108q15 4 30 0c0 24-30 24-30 0Z" fill="#633c30" />
              <path d="M91 121q9-9 18 0" fill="#e89a8b" stroke="none" />
            </g>
          ) : listening ? (
            <path d="M91 112q9 8 18 0" fill="none" />
          ) : (
            <path d="M84 108q16 19 32 0" fill="#fff8e4" />
          )}
          {listening && (
            <g fill="none" stroke="#315f86">
              <path d="M43 77c-4-70 118-70 114 0" strokeWidth="7" />
              <path d="M43 78v19m114-19v19" strokeWidth="13" />
              <path d="M158 97q1 20-25 20" strokeWidth="3" />
              <rect x="125" y="114" width="12" height="6" rx="3" fill="#315f86" stroke="none" />
            </g>
          )}
          <path d="m76 139 24 9 24-9-5 14-19 5-19-5Z" fill="#e9c980" stroke="#b79551" strokeWidth="1.5" />
          <path d="m109 155 8 20 10-8-8-16" fill="#e9c980" stroke="#b79551" strokeWidth="1.5" />
        </g>
        <g className="buddy-arm-right" style={writing ? { display: "none" } : undefined}>
          <path
            d={thinking ? "M137 158q15-8-4-36" : encouraging ? "M137 158q16 3 21-15" : "M137 156q19-3 24-27"}
            fill="none"
            stroke="#6099c5"
            strokeWidth="17"
          />
          {thinking ? (
            <g fill={`url(#${face})`}>
              <ellipse cx="131" cy="120" rx="9" ry="11" transform="rotate(-25 131 120)" />
              <path d="m129 116-7-10q-1-4 3-3l9 10" />
            </g>
          ) : encouraging ? (
            <path d="m151 148-1-15q0-5 4-5l3-9q3-5 6 0l-1 13h7q5 0 3 6l-4 13h-13Z" fill={`url(#${face})`} />
          ) : (
            <g className="buddy-wave">
              <path
                d="m155 132-5-10q-2-5 2-6l5 5-1-15q0-5 4-4l3 16 3-17q2-4 5-1l-1 19 5-11q3-4 5 0l-5 18q-3 12-12 12Z"
                fill={`url(#${face})`}
                strokeWidth="2"
              />
              <path d="M157 123q7-3 10 3" fill="none" stroke="#bd8051" strokeWidth="1.5" />
            </g>
          )}
        </g>
        {celebrating && (
          <g className="buddy-sparkles" stroke="#c09a4d" fill="#f1d586" strokeWidth="1.5">
            <path d="m32 35 3 8 8 3-8 3-3 8-3-8-8-3 8-3Z" />
            <path d="m164 23 3 8 8 3-8 3-3 8-3-8-8-3 8-3Z" />
            <path d="m181 108 2 5 5 2-5 2-2 5-2-5-5-2 5-2Z" />
            <path d="m48 17 3 5m133 41-5 3M20 111l-5 3" stroke="#b7684b" strokeWidth="3" />
          </g>
        )}
        {thinking && (
          <g className="buddy-thought" fill="#fff6d7" stroke="#b79551" strokeWidth="1.5">
            <circle cx="166" cy="37" r="14" />
            <circle cx="151" cy="54" r="3" />
            <path d="M162 33q0-7 7-4 6 4-2 8v3m0 5v.1" fill="none" stroke="#87643e" strokeWidth="2.5" />
          </g>
        )}
      </g>
    </svg>
  );
}
