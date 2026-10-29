import type { Dimension } from "../../../api/contract";
import { DIMENSION_LABEL } from "../../../components/labels";
import { formatViDecimal } from "../../../lib/viNumber";
import { RADAR_AXES } from "./helpers";

const S = 360;
const C = S / 2;
const R = 100;
const RINGS = [
  { value: 40, className: "stroke-orange-300" },
  { value: 60, className: "stroke-yellow-400" },
  { value: 75, className: "stroke-emerald-400" },
  { value: 90, className: "stroke-emerald-700" },
];

function at(index: number, value: number): [number, number] {
  const angle = -Math.PI / 2 + (index * 2 * Math.PI) / RADAR_AXES.length;
  const r = (R * value) / 100;
  return [C + r * Math.cos(angle), C + r * Math.sin(angle)];
}

function ring(value: number): string {
  return RADAR_AXES.map((_, i) =>
    at(i, value)
      .map((v) => v.toFixed(1))
      .join(","),
  ).join(" ");
}

/**
 * The radar chart of §24 on 0–100. Rings mark the zone limits of §25 (40, 60, 75, 90). An axis without
 * enough evidence (DI-1) has no point and says so, as Retention does in the example of §55.
 */
export function RadarChart({ values }: { values: Record<Dimension, number | null> }) {
  const known = RADAR_AXES.map((d, i) => ({ d, i, v: values[d] })).filter(
    (a): a is { d: Dimension; i: number; v: number } => a.v !== null,
  );
  const polygon = known
    .map(({ i, v }) =>
      at(i, v)
        .map((n) => n.toFixed(1))
        .join(","),
    )
    .join(" ");
  const summary = RADAR_AXES.map(
    (d) => `${DIMENSION_LABEL[d]} ${values[d] === null ? "chưa đủ dữ liệu" : formatViDecimal(values[d])}`,
  ).join(", ");
  return (
    <figure className="flex flex-col items-center">
      <svg
        data-chart
        viewBox={`0 0 ${S} ${S}`}
        width={S}
        height={S}
        className="max-w-full"
        role="img"
        aria-label={`Biểu đồ radar 6 chiều: ${summary}`}
      >
        <polygon points={ring(100)} className="fill-slate-50 stroke-slate-300" strokeWidth={1} />
        {RINGS.map((r) => (
          <polygon
            key={r.value}
            points={ring(r.value)}
            className={`fill-none ${r.className}`}
            strokeWidth={1}
            strokeDasharray="3 3"
          />
        ))}
        {RADAR_AXES.map((_, i) => {
          const [x, y] = at(i, 100);
          return <line key={i} x1={C} y1={C} x2={x} y2={y} className="stroke-slate-300" strokeWidth={1} />;
        })}
        {RINGS.map((r) => {
          const [x, y] = at(0, r.value);
          return (
            <text key={r.value} x={x + 4} y={y + 3} className="fill-slate-400 text-[9px] tabular-nums">
              {r.value}
            </text>
          );
        })}
        {known.length >= 3 ? (
          <polygon
            points={polygon}
            className="chart-radar fill-brand-500/25 stroke-brand-700"
            strokeWidth={2}
          />
        ) : (
          known.map(({ i, v }) => {
            const [x, y] = at(i, v);
            return <line key={i} x1={C} y1={C} x2={x} y2={y} className="stroke-brand-700" strokeWidth={2} />;
          })
        )}
        {known.map(({ i, v }) => {
          const [x, y] = at(i, v);
          return <circle key={i} cx={x} cy={y} r={4} className="fill-brand-700" />;
        })}
        {RADAR_AXES.map((d, i) => {
          const [x, y] = at(i, 100);
          const dx = x - C;
          const anchor = dx > 8 ? "start" : dx < -8 ? "end" : "middle";
          const ox = anchor === "start" ? 8 : anchor === "end" ? -8 : 0;
          const oy = y < C - 10 ? -18 : y > C + 10 ? 16 : -2;
          const value = values[d];
          return (
            <text key={d} x={x + ox} y={y + oy} textAnchor={anchor} className="text-[12px]">
              <tspan className="fill-slate-700 font-semibold">{DIMENSION_LABEL[d]}</tspan>
              <tspan
                x={x + ox}
                dy={14}
                className={value === null ? "fill-slate-400 text-[11px]" : "fill-ink font-bold tabular-nums"}
              >
                {value === null ? "chưa đủ dữ liệu" : formatViDecimal(value)}
              </tspan>
            </text>
          );
        })}
      </svg>
    </figure>
  );
}
