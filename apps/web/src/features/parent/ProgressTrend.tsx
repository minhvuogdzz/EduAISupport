import type { ParentChildView } from "../../api/contract";
import { useElementWidth } from "../../lib/useElementWidth";

type Day = ParentChildView["trend"][number];

function dayMonth(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${day}/${month}`;
}

/**
 * Four weeks of progress for the parent (PART 27.1 "xu hướng 4 tuần"): one series, the topics passed so
 * far, as a step line; below it, the days the child learned. Two separate marks, never a second axis.
 * Each day has a native tooltip, and the list after the chart says the same for screen readers.
 */
export function ProgressTrend({ trend, total }: { trend: Day[]; total: number }) {
  const [frame, W] = useElementWidth(640);
  const H = 220;
  const left = 30;
  const right = 12;
  const top = 12;
  const bottom = 26;
  const plotW = W - left - right;
  const step = plotW / Math.max(trend.length, 1);
  const y = (v: number) => top + (1 - v / Math.max(total, 1)) * (H - top - bottom);
  const x = (i: number) => left + i * step;
  const path = trend
    .map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.passed)} L${x(i) + step},${y(d.passed)}`)
    .join(" ");
  const area = `${path} L${x(trend.length)},${y(0)} L${x(0)},${y(0)} Z`;
  const ticks = Array.from({ length: total + 1 }, (_, i) => i).filter((v) => total <= 7 || v % 2 === 0);
  const last = trend.at(-1);
  return (
    <figure ref={frame} className="flex flex-col gap-3">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="max-w-full"
        role="img"
        aria-label="Số bài con đã qua theo từng ngày trong 4 tuần"
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={left} x2={W - right} y1={y(t)} y2={y(t)} className="stroke-slate-200" strokeWidth={1} />
            <text
              x={left - 8}
              y={y(t) + 4}
              textAnchor="end"
              className="fill-slate-500 text-[11px] tabular-nums"
            >
              {t}
            </text>
          </g>
        ))}
        <path d={area} className="fill-brand-100" />
        <path d={path} fill="none" className="stroke-brand-700" strokeWidth={2} strokeLinejoin="round" />
        {trend.map((d, i) => (
          <rect key={d.date} x={x(i)} y={top} width={step} height={H - top - bottom} fill="transparent">
            <title>{`${dayMonth(d.date)}: đã qua ${d.passed}/${total} bài${d.studied ? " · có học" : ""}`}</title>
          </rect>
        ))}
        {trend.map((d, i) =>
          i % 7 === 0 || i === trend.length - 1 ? (
            <text
              key={d.date}
              x={x(i) + step / 2}
              y={H - 8}
              textAnchor="middle"
              className="fill-slate-500 text-[11px]"
            >
              {dayMonth(d.date)}
            </text>
          ) : null,
        )}
        {last && (
          <text
            x={W - right}
            y={y(last.passed) - 7}
            textAnchor="end"
            className="fill-slate-900 text-[12px] font-semibold"
          >
            {last.passed}/{total} bài
          </text>
        )}
      </svg>
      <div>
        <ol className="grid grid-cols-[repeat(28,minmax(0,1fr))] gap-0.5" aria-hidden="true">
          {trend.map((d) => (
            <li
              key={d.date}
              title={`${dayMonth(d.date)}: ${d.studied ? "có học" : "không học"}`}
              className={`h-3 rounded-sm ${d.studied ? "bg-orange-400" : "bg-slate-100"}`}
            />
          ))}
        </ol>
        <p className="mt-1.5 flex items-center gap-1.5 text-sm text-slate-600">
          <span className="inline-block size-3 rounded-sm bg-orange-400" /> ngày con có học
        </p>
      </div>
      <ul className="sr-only">
        {trend
          .filter((d) => d.studied)
          .map((d) => (
            <li key={d.date}>
              {dayMonth(d.date)}: có học, đã qua {d.passed}/{total} bài
            </li>
          ))}
      </ul>
    </figure>
  );
}
