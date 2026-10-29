import type { TeacherStudentView } from "../../../api/contract";
import { RESOLUTION_LABEL } from "../../../components/labels";
import { useElementWidth } from "../../../lib/useElementWidth";

type Day = TeacherStudentView["activity"][number];

const PARTS = [
  {
    key: "independent",
    label: RESOLUTION_LABEL.INDEPENDENT,
    fill: "fill-emerald-500",
    swatch: "bg-emerald-500",
  },
  { key: "supported", label: RESOLUTION_LABEL.SUPPORTED, fill: "fill-sky-400", swatch: "bg-sky-400" },
  { key: "worked", label: RESOLUTION_LABEL.WORKED, fill: "fill-amber-400", swatch: "bg-amber-400" },
  { key: "unresolved", label: RESOLUTION_LABEL.UNRESOLVED, fill: "fill-rose-400", swatch: "bg-rose-400" },
] as const;

const SHOWN = 14;

function dayMonth(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${day}/${month}`;
}

function describe(d: Day): string {
  const parts = PARTS.filter((p) => d[p.key] > 0).map((p) => `${d[p.key]} ${p.label.toLowerCase()}`);
  return `${dayMonth(d.date)}: ${parts.join(", ") || "không có câu nào"}; ${d.hints} gợi ý${
    d.passed ? `; qua ${d.passed} bài` : ""
  }`;
}

/**
 * The learning activity timeline of khung Toán §56: per day, how each item ended (stacked), the hints
 * asked and the KCs passed (★). The last 14 days with activity; each bar has a tooltip and a sentence in
 * the list after the chart.
 */
export function ActivityChart({ days }: { days: Day[] }) {
  const [frame, W] = useElementWidth(560);
  const shown = days.slice(-SHOWN);
  const H = 200;
  const left = 28;
  const top = 22;
  const bottom = 34;
  const max = Math.max(1, ...shown.map((d) => PARTS.reduce((n, p) => n + d[p.key], 0)));
  const slot = (W - left - 8) / Math.max(shown.length, 1);
  const barW = Math.min(36, slot * 0.6);
  const unit = (H - top - bottom) / max;
  return (
    <figure ref={frame} className="flex flex-col gap-2">
      <svg
        data-chart
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="max-w-full"
        role="img"
        aria-label="Hoạt động học theo ngày: số câu theo cách hoàn thành, số gợi ý và bài đã qua"
      >
        <line x1={left} x2={W - 8} y1={H - bottom} y2={H - bottom} className="stroke-slate-300" />
        <text x={left - 6} y={top + 4} textAnchor="end" className="fill-slate-500 text-[10px] tabular-nums">
          {max}
        </text>
        <text x={left - 6} y={H - bottom + 4} textAnchor="end" className="fill-slate-500 text-[10px]">
          0
        </text>
        {shown.map((d, i) => {
          const cx = left + slot * i + slot / 2;
          let base = H - bottom;
          const total = PARTS.reduce((n, p) => n + d[p.key], 0);
          return (
            <g key={d.date}>
              <title>{describe(d)}</title>
              {PARTS.map((p) => {
                const h = d[p.key] * unit;
                base -= h;
                return h > 0 ? (
                  <rect
                    key={p.key}
                    x={cx - barW / 2}
                    y={base}
                    width={barW}
                    height={h}
                    className={`chart-bar ${p.fill}`}
                    style={{ transformOrigin: `${cx}px ${H - bottom}px`, animationDelay: `${i * 55}ms` }}
                  />
                ) : null;
              })}
              <text
                x={cx}
                y={H - bottom - total * unit - (d.passed ? 16 : 5)}
                textAnchor="middle"
                className="fill-slate-700 text-[11px] font-semibold tabular-nums"
              >
                {total}
              </text>
              {d.passed > 0 && (
                <text
                  x={cx}
                  y={H - bottom - total * unit - 4}
                  textAnchor="middle"
                  className="fill-amber-500 text-[12px]"
                >
                  ★
                </text>
              )}
              <text x={cx} y={H - bottom + 14} textAnchor="middle" className="fill-slate-500 text-[11px]">
                {dayMonth(d.date)}
              </text>
              <text x={cx} y={H - bottom + 27} textAnchor="middle" className="fill-slate-500 text-[10px]">
                {d.hints} gợi ý
              </text>
            </g>
          );
        })}
      </svg>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-700" aria-label="Chú giải">
        {PARTS.map((p) => (
          <li key={p.key} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={`inline-block size-3 rounded-sm ${p.swatch}`} />
            {p.label}
          </li>
        ))}
        <li>★ ngày qua bài</li>
      </ul>
      <ol className="sr-only">
        {shown.map((d) => (
          <li key={d.date}>{describe(d)}</li>
        ))}
      </ol>
    </figure>
  );
}
