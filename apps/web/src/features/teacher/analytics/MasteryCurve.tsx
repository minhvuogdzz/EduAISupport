import { useState } from "react";
import type { CurvePoint, TeacherNodeDetail } from "../../../api/contract";
import { useElementWidth } from "../../../lib/useElementWidth";
import { formatViDecimal } from "../../../lib/viNumber";

/**
 * How the student went from not understanding to understanding: the chapter's overall mastery (periods not
 * met count 0) after every change of a period's score, across the sessions, with a mark where a period was
 * passed. Features a dynamic rising stroke animation, a quiet filled area, and interactive milestone tooltips.
 */
export function MasteryCurve({ points, nodes }: { points: CurvePoint[]; nodes: TeacherNodeDetail[] }) {
  const [frame, W] = useElementWidth(560);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (points.length === 0) return <p className="text-slate-600">Chưa có bằng chứng nào.</p>;
  const H = 220;
  const left = 34;
  const right = 12;
  const top = 16;
  const bottom = 26;
  const plotW = W - left - right;
  const x = (i: number) => left + (points.length <= 1 ? plotW / 2 : (i * plotW) / (points.length - 1));
  const y = (v: number) => top + (1 - v / 100) * (H - top - bottom);
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.mastery)}`).join(" ");

  // Area path closing at the bottom line for a soft fill
  const lastX = x(points.length - 1);
  const firstX = x(0);
  const bottomY = y(0);
  const areaPath = `${line} L${lastX},${bottomY} L${firstX},${bottomY} Z`;

  const names = new Map(nodes.map((n) => [n.node_id, n.name]));
  const passes = points.map((p, i) => ({ p, i })).filter(({ p }) => p.passed);

  const firstScore = points[0]?.mastery ?? 0;
  const latestScore = points[points.length - 1]?.mastery ?? 0;
  const growth = Math.max(0, latestScore - firstScore);

  return (
    <figure ref={frame} className="flex flex-col gap-3 rounded-2xl bg-white p-2">
      {/* Dynamic progress badge */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs">
        <span className="font-semibold text-slate-700">Đồ thị tiến trình hiểu bài theo thời gian</span>
        <div className="flex items-center gap-2">
          {growth > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 font-bold text-emerald-700 ring-1 ring-emerald-200">
              <span aria-hidden="true">↑</span> Tăng +{formatViDecimal(growth)} điểm
            </span>
          )}
          <span className="rounded-full bg-sky-50 px-2.5 py-0.5 font-medium text-sky-800 ring-1 ring-sky-200">
            Hiện tại: {formatViDecimal(latestScore)}/100
          </span>
        </div>
      </div>

      <div className="relative">
        <svg
          data-chart
          viewBox={`0 0 ${W} ${H}`}
          width={W}
          height={H}
          className="max-w-full overflow-visible"
          role="img"
          aria-label="Điểm hiểu bài của cả chương sau từng bằng chứng"
        >
          {/* Grid lines */}
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={v}>
              <line
                x1={left}
                x2={W - right}
                y1={y(v)}
                y2={y(v)}
                className="stroke-slate-100"
                strokeWidth={1}
              />
              <text x={left - 6} y={y(v) + 3.5} textAnchor="end" className="fill-slate-400 text-[10px]">
                {v}
              </text>
            </g>
          ))}

          {/* 75% Mastery threshold reference line */}
          <line
            x1={left}
            x2={W - right}
            y1={y(75)}
            y2={y(75)}
            className="stroke-emerald-400/80"
            strokeWidth={1.5}
            strokeDasharray="4 3"
          />
          <text
            x={W - right}
            y={y(75) - 4}
            textAnchor="end"
            className="fill-emerald-600 text-[9px] font-semibold"
          >
            Ngưỡng điểm 75/100
          </text>

          {/* Gradient area underneath */}
          <path d={areaPath} fill="#e0edf8" className="chart-area" />

          {/* Animated rising mastery curve line */}
          <path
            d={line}
            key={line}
            pathLength={1}
            fill="none"
            stroke="#3f76a3"
            strokeWidth={2.75}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="chart-line"
          />

          {/* Passing milestone circles */}
          {passes.map(({ p, i }) => {
            const cx = x(i);
            const cy = y(p.mastery);
            const isHovered = hoveredIdx === i;
            return (
              <g
                key={`${p.passed}-${i}`}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
                className="chart-point cursor-pointer"
                style={{ animationDelay: `${(i / Math.max(1, points.length - 1)) * 1600}ms` }}
              >
                {/* Pulsing beacon ring for milestone pass */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={8}
                  fill="#10b981"
                  opacity={isHovered ? 0.4 : 0.2}
                  className="transition-opacity"
                />
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 6 : 4.5}
                  className="fill-emerald-600 stroke-white transition-all duration-200"
                  strokeWidth={2}
                >
                  <title>
                    Qua bài {names.get(p.passed ?? "") ?? p.passed}: điểm chương {formatViDecimal(p.mastery)}
                  </title>
                </circle>
              </g>
            );
          })}

          <text x={left} y={H - 6} className="fill-slate-400 text-[10px]">
            Bằng chứng đầu
          </text>
          <text x={W - right} y={H - 6} textAnchor="end" className="fill-slate-400 text-[10px]">
            Mới nhất
          </text>
        </svg>
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-slate-700">
        {passes.map(({ p, i }) => (
          <li
            key={`${p.passed}-${i}-l`}
            className="inline-flex items-center gap-1.5 rounded-md bg-slate-50 px-2 py-0.5"
          >
            <span aria-hidden="true" className="size-2 rounded-full bg-emerald-600" />
            <span className="font-medium text-slate-800">{names.get(p.passed ?? "") ?? p.passed}:</span>
            <span className="font-bold text-emerald-700">{formatViDecimal(p.mastery)}/100</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
