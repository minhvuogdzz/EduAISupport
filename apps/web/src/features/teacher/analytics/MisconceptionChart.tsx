import { formatViDecimal } from "../../../lib/viNumber";

export interface MisconceptionBar {
  id: string;
  name: string;
  severity: string;
  count: number;
  /** Percentage of all detections. */
  share: number;
  /** One line under the bar: where, how many students, still active or not. */
  note: string;
}

/**
 * The misconception chart (khung Toán §28): one bar per misconception, its share of every detection, the
 * critical ones in rose. The bars are labelled with their numbers, so colour is not needed to read them.
 */
export function MisconceptionChart({ items, empty }: { items: MisconceptionBar[]; empty: string }) {
  if (items.length === 0) return <p className="text-slate-600">{empty}</p>;
  return (
    <ul className="flex flex-col gap-3">
      {items.map((m) => (
        <li key={m.id}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-medium">
              {m.name}
              {m.severity === "CRITICAL" && (
                <span className="ml-2 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-800 ring-1 ring-rose-200">
                  nghiêm trọng
                </span>
              )}
            </span>
            <span className="shrink-0 text-sm font-semibold tabular-nums">
              {formatViDecimal(m.share)}% · {m.count} lần
            </span>
          </div>
          <div
            className="mt-1 h-3 rounded-full bg-slate-100"
            role="img"
            aria-label={`${m.name}: ${formatViDecimal(m.share)}% số lần phát hiện lỗi`}
          >
            <div
              className={`h-3 rounded-full ${m.severity === "CRITICAL" ? "bg-rose-500" : "bg-amber-400"}`}
              style={{ width: `${Math.max(m.share, 2)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-slate-600">{m.note}</p>
        </li>
      ))}
    </ul>
  );
}
