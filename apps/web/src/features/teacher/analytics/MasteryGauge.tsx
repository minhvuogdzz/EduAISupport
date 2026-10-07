import { LEVEL_NAME } from "../../../components/labels";
import { formatViDecimal } from "../../../lib/viNumber";
import { CONFIDENCE_FLOOR, ZONES, zoneOf } from "./zones";

const W = 260;
const H = 134;
const CX = 130;
const CY = 118;
const R = 96;
const TICKS = [0, 40, 60, 75, 90, 100];

function point(value: number, radius: number): [number, number] {
  const angle = Math.PI * (1 - value / 100);
  return [CX + radius * Math.cos(angle), CY - radius * Math.sin(angle)];
}

function arc(from: number, to: number): string {
  const [x0, y0] = point(from, R);
  const [x1, y1] = point(to, R);
  return `M${x0.toFixed(2)},${y0.toFixed(2)} A${R},${R} 0 0 1 ${x1.toFixed(2)},${y1.toFixed(2)}`;
}

/**
 * The mastery gauge with its confidence bar (khung Toán §56.1, blueprint 27.2): a half dial in the five
 * zones of §25 with a needle on M, the number in words below; then how sure the system is (§21). Below the
 * confidence floor of DI-7 the number stays, with a warning (PART 27.3, item 7).
 */
export function MasteryGauge({
  mastery,
  confidence,
  level,
  caption,
}: {
  mastery: number | null;
  confidence: number | null;
  level: number | null;
  caption: string;
}) {
  const bands = [...ZONES].reverse();
  const needle = mastery === null ? null : point(mastery, R - 26);
  const label =
    mastery === null
      ? `${caption}: chưa có bằng chứng`
      : `${caption}: M ${formatViDecimal(mastery)}, vùng ${zoneOf(mastery).name}${
          level === null ? "" : `, mức ${level} ${LEVEL_NAME[level]}`
        }`;
  return (
    <figure className="flex flex-col items-center gap-3">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="max-w-full"
        role="img"
        aria-label={label}
      >
        {bands.map((zone, i) => {
          const to = bands[i + 1]?.from ?? 100;
          return (
            <path
              key={zone.range}
              d={arc(zone.from + (zone.from === 0 ? 0 : 0.6), to - (to === 100 ? 0 : 0.6))}
              className={`fill-none ${zone.stroke} ${mastery === null ? "opacity-25" : ""}`}
              strokeWidth={18}
            />
          );
        })}
        {TICKS.map((t) => {
          const [x, y] = point(t, R + 17);
          return (
            <text
              key={t}
              x={x}
              y={y + 4}
              textAnchor="middle"
              className="fill-slate-500 text-[10px] tabular-nums"
            >
              {t}
            </text>
          );
        })}
        {needle && (
          <>
            <line
              x1={CX}
              y1={CY}
              x2={needle[0]}
              y2={needle[1]}
              className="stroke-ink"
              strokeWidth={3}
              strokeLinecap="round"
              strokeDasharray={confidence !== null && confidence < CONFIDENCE_FLOOR ? "4 4" : undefined}
            />
            <circle cx={CX} cy={CY} r={6} className="fill-ink" />
          </>
        )}
      </svg>
      <figcaption className="-mt-1 text-center">
        <span className="block text-3xl font-bold tabular-nums">
          {mastery === null ? "–" : formatViDecimal(mastery)}
        </span>
        <span className="block text-sm text-slate-600">{caption}</span>
        <span className="block font-semibold">
          {mastery === null || level === null ? "Chưa có bằng chứng" : `Mức ${level} · ${LEVEL_NAME[level]}`}
        </span>
      </figcaption>
      {confidence !== null && <ConfidenceBar confidence={confidence} />}
    </figure>
  );
}

/** How sure the system is about M (§21, DI-11), with the floor of DI-7 marked on the bar. */
export function ConfidenceBar({ confidence }: { confidence: number }) {
  const low = confidence < CONFIDENCE_FLOOR;
  return (
    <div className="w-full max-w-60">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-slate-600">Độ tin cậy</span>
        <span className="font-semibold tabular-nums">{formatViDecimal(confidence)}</span>
      </div>
      <div
        className="relative mt-1 h-2.5 rounded-full bg-slate-100"
        role="img"
        aria-label={`Độ tin cậy ${formatViDecimal(confidence)} trên 100`}
      >
        <div
          className={`h-2.5 rounded-full ${low ? "bg-amber-400" : "bg-sky-500"}`}
          style={{ width: `${Math.min(confidence, 100)}%` }}
        />
        <span
          aria-hidden="true"
          className="absolute -top-1 h-4.5 w-0.5 rounded bg-slate-600"
          style={{ left: `${CONFIDENCE_FLOOR}%` }}
        />
      </div>
      <p className={`mt-1 text-xs ${low ? "font-medium text-amber-800" : "text-slate-500"}`}>
        {low
          ? "Dưới 30: chưa đủ dữ liệu, điểm chỉ là ước lượng ban đầu (DI-7)"
          : "Vạch đứng là mức 30: dưới mức này là chưa đủ dữ liệu (DI-7)"}
      </p>
    </div>
  );
}
