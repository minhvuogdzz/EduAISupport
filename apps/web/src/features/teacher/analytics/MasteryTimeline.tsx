import type { TeacherStudentView } from "../../../api/contract";
import { useElementWidth } from "../../../lib/useElementWidth";
import { formatViDecimal } from "../../../lib/viNumber";
import { ZONES } from "./zones";

type Point = TeacherStudentView["timeline"][number];

/** Light tints of the §25 zones, drawn behind the line so each point reads against its zone. */
const BAND_TINT: Record<string, string> = {
  "90–100": "fill-emerald-100",
  "75–89": "fill-emerald-50",
  "60–74": "fill-yellow-50",
  "40–59": "fill-orange-50",
  "0–39": "fill-red-50",
};

function dayMonth(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${day}/${month}`;
}

/**
 * The mastery timeline of khung Toán §27: the overall M of §23 at the end of each day with new evidence
 * (DI-26), over the zones of §25. One series, one axis; each point has a native tooltip and the list after
 * the chart repeats the values for screen readers.
 */
export function MasteryTimeline({ points }: { points: Point[] }) {
  const [frame, W] = useElementWidth(560);
  const H = 220;
  const left = 34;
  const right = 16;
  const top = 12;
  const bottom = 26;
  const plotW = W - left - right;
  const y = (v: number) => top + (1 - v / 100) * (H - top - bottom);
  const x = (i: number) => left + (points.length <= 1 ? plotW / 2 : (i * plotW) / (points.length - 1));
  const bands = [...ZONES].reverse();
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.mastery)}`).join(" ");
  const every = Math.max(1, Math.ceil(points.length / 8));
  return (
    <figure ref={frame} className="flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="max-w-full"
        role="img"
        aria-label="Điểm hiểu bài tổng của chương theo từng ngày học"
      >
        {bands.map((zone, i) => {
          const to = bands[i + 1]?.from ?? 100;
          return (
            <rect
              key={zone.range}
              x={left}
              y={y(to)}
              width={plotW}
              height={y(zone.from) - y(to)}
              className={BAND_TINT[zone.range]}
            />
          );
        })}
        {[0, 40, 60, 75, 90, 100].map((t) => (
          <text
            key={t}
            x={left - 6}
            y={y(t) + 4}
            textAnchor="end"
            className="fill-slate-500 text-[10px] tabular-nums"
          >
            {t}
          </text>
        ))}
        {points.length > 1 && (
          <path d={line} fill="none" className="stroke-brand-700" strokeWidth={2.5} strokeLinejoin="round" />
        )}
        {points.map((p, i) => (
          <g key={p.date}>
            <circle
              cx={x(i)}
              cy={y(p.mastery)}
              r={5}
              className="fill-white stroke-brand-700"
              strokeWidth={2.5}
            >
              <title>{`${dayMonth(p.date)}: M ${formatViDecimal(p.mastery)}`}</title>
            </circle>
            {(i % every === 0 || i === points.length - 1) && (
              <text x={x(i)} y={H - 8} textAnchor="middle" className="fill-slate-500 text-[11px]">
                {dayMonth(p.date)}
              </text>
            )}
          </g>
        ))}
        {points.length > 0 && (
          <text
            x={Math.min(x(points.length - 1), W - right - 4)}
            y={y(points[points.length - 1].mastery) - 10}
            textAnchor="end"
            className="fill-ink text-[12px] font-bold tabular-nums"
          >
            {formatViDecimal(points[points.length - 1].mastery)}
          </text>
        )}
      </svg>
      {points.length < 2 && (
        <p className="text-sm text-slate-600">Cần thêm ít nhất một ngày học nữa để thấy xu hướng.</p>
      )}
      <ol className="sr-only">
        {points.map((p) => (
          <li key={p.date}>
            {dayMonth(p.date)}: M {formatViDecimal(p.mastery)}
          </li>
        ))}
      </ol>
    </figure>
  );
}
