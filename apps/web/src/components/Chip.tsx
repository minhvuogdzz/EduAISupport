import type { ReactNode } from "react";

const TONES = {
  slate: "bg-slate-100 text-slate-800",
  teal: "bg-teal-100 text-teal-900",
  amber: "bg-amber-100 text-amber-900",
  rose: "bg-rose-100 text-rose-900",
  sky: "bg-sky-100 text-sky-900",
  emerald: "bg-emerald-100 text-emerald-900",
} as const;

export type ChipTone = keyof typeof TONES;

interface ChipProps {
  tone?: ChipTone;
  mono?: boolean;
  title?: string;
  children: ReactNode;
}

export function Chip({ tone = "slate", mono = false, title, children }: ChipProps) {
  return (
    <span
      title={title}
      className={`inline-block rounded-full px-2 py-0.5 text-xs leading-5 font-medium ${TONES[tone]} ${
        mono ? "font-mono" : ""
      }`}
    >
      {children}
    </span>
  );
}
