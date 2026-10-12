import type { CurvePoint, TeacherNodeDetail } from "../../../api/contract";
import { useElementWidth } from "../../../lib/useElementWidth";
import { formatViDecimal } from "../../../lib/viNumber";

/**
 * How the student went from not understanding to understanding: the chapter's overall mastery (periods not
 * met count 0) after every change of a period's score, across the sessions, with a mark where a period was
 * passed. The list after the chart names each pass and its score, for screen readers.
 */
export function MasteryCurve({ points, nodes }: { points: CurvePoint[]; nodes: TeacherNodeDetail[] }) {
  const [frame, W] = useElementWidth(560);
  if (points.length === 0) return <p className="text-slate-600">Chưa có bằng chứng nào.</p>;
  const H = 220;
  const left = 34;
  const right = 12;
  const top = 12;
  const bottom = 24;
  const plotW = W - left - right;
  const x = (i: number) => left + (points.length <= 1 ? plotW / 2 : (i * plotW) / (points.length - 1));
  const y = (v: number) => top + (1 - v / 100) * (H - top - bottom);
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.mastery)}`).join(" ");
  const names = new Map(nodes.map((n) => [n.node_id, n.name]));
  const passes = points.map((p, i) => ({ p, i })).filter(({ p }) => p.passed);
  return (
    <figure ref={frame} className="flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="max-w-full"
        role="img"
        aria-label="Điểm hiểu bài của cả chương sau từng bằng chứng"
      >
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line x1={left} x2={W - right} y1={y(v)} y2={y(v)} className="stroke-slate-200" />
            <text x={left - 6} y={y(v) + 4} textAnchor="end" className="fill-slate-500 text-[10px]">
              {v}
            </text>
          </g>
        ))}
        <line
          x1={left}
          x2={W - right}
          y1={y(75)}
          y2={y(75)}
          className="stroke-emerald-400"
          strokeDasharray="4 3"
        />
        <path d={line} fill="none" className="stroke-brand-700" strokeWidth={2} />
        {passes.map(({ p, i }) => (
          <g key={`${p.passed}-${i}`}>
            <circle
              cx={x(i)}
              cy={y(p.mastery)}
              r={4.5}
              className="fill-emerald-600 stroke-white"
              strokeWidth={1.5}
            >
              <title>
                Qua bài {names.get(p.passed ?? "") ?? p.passed}: điểm chương {formatViDecimal(p.mastery)}
              </title>
            </circle>
          </g>
        ))}
        <text x={left} y={H - 6} className="fill-slate-500 text-[10px]">
          bằng chứng đầu
        </text>
        <text x={W - right} y={H - 6} textAnchor="end" className="fill-slate-500 text-[10px]">
          mới nhất
        </text>
      </svg>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-700">
        {passes.map(({ p, i }) => (
          <li key={`${p.passed}-${i}-l`}>
            <span aria-hidden="true" className="text-emerald-700">
              ●
            </span>{" "}
            {names.get(p.passed ?? "") ?? p.passed}: {formatViDecimal(p.mastery)}
          </li>
        ))}
      </ul>
    </figure>
  );
}
