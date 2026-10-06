import { useState, type ReactNode } from "react";

import {
  DIMENSIONS,
  type DecisionEntry,
  type EvidenceEntry,
  type MasteryPoint,
  type ReportNode,
  type TeachingReport,
} from "../../api/contract";
import { Chip, type ChipTone } from "../../components/Chip";
import {
  DIMENSION_LABEL,
  DIMENSION_WEIGHT,
  EVIDENCE_REASON_LABEL,
  LEVEL_LABEL,
  MISSING_LABEL,
  NODE_STATUS_LABEL,
  RULE_LABEL,
  TEACH_ACTION_LABEL,
} from "../../components/labels";
import { useElementWidth } from "../../lib/useElementWidth";
import { formatViDecimal, formatViTime } from "../../lib/viNumber";
import { KnowledgeMap } from "../teaching/KnowledgeMap";

const SHOWN = 12;

/**
 * "Bộ não gia sư" for the teacher: how the tutor scored each node and why it took each step, replayed
 * from the session's events (rule 3). The map shows M per node; the selected node shows its score over
 * time, its seven dimensions, the pass rule and every piece of evidence; below, every decision of the
 * teaching policy with its rule.
 */
export function BrainPanel({ report }: { report: TeachingReport }) {
  const [chosen, setChosen] = useState<string | null>(null);
  const selectedId =
    chosen ?? report.current_node_id ?? report.nodes.find((n) => n.mastery !== null)?.node_id;
  const node = report.nodes.find((n) => n.node_id === selectedId) ?? report.nodes[0];
  const names = new Map(report.nodes.map((n) => [n.node_id, n.name]));
  return (
    <div className="flex flex-col gap-6">
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <section
          aria-labelledby="map-title"
          className="rounded-2xl bg-white p-4 ring-1 ring-slate-200 xl:sticky xl:top-4"
        >
          <h3 id="map-title" className="font-semibold">
            Cây tri thức · {report.chapter.title}
          </h3>
          <p className="mb-3 text-sm text-slate-600">
            Bấm vào một bài để xem điểm, bằng chứng và quyết định.
          </p>
          <KnowledgeMap
            nodes={report.nodes.map((n) => ({ ...n, level: n.mastery === null ? null : n.level }))}
            relations={report.relations}
            title={`Cây tri thức chương ${report.chapter.title}, điểm M từng bài`}
            showMastery
            selectedId={node?.node_id ?? null}
            onSelect={setChosen}
          />
        </section>
        {node && <NodeDetail node={node} report={report} />}
      </div>
      <DecisionTimeline decisions={report.decisions} names={names} />
      {report.earlier_sessions ? (
        <p className="text-sm text-slate-700">
          Điểm tính cả {report.earlier_sessions} buổi học trước của {report.session.student_display_name} ở
          chương này: cô nhớ con đã học tới đâu. Bằng chứng từ buổi trước có nhãn "buổi trước".
        </p>
      ) : null}
      <p className="text-xs text-slate-500">
        Tính lại từ sự kiện của buổi học ·{" "}
        {Object.entries(report.versions)
          .map(([key, version]) => `${key}: ${version}`)
          .join(" · ")}
      </p>
    </div>
  );
}

function NodeDetail({ node, report }: { node: ReportNode; report: TeachingReport }) {
  const evidence = report.evidence.filter((e) => e.node_id === node.node_id);
  const trace = report.trace.filter((t) => t.node_id === node.node_id && t.mastery !== null);
  const titleId = `node-${node.node_id}`;
  const statusTone: ChipTone =
    node.status === "PASSED"
      ? "emerald"
      : node.status === "CURRENT"
        ? "teal"
        : node.status === "STOPPED"
          ? "rose"
          : "slate";
  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-5 rounded-2xl bg-white p-4 ring-1 ring-slate-200"
    >
      <header className="flex flex-wrap items-center gap-2">
        <h3 id={titleId} className="text-xl font-semibold">
          {node.name}
        </h3>
        <Chip tone={statusTone}>{NODE_STATUS_LABEL[node.status]}</Chip>
        <Chip mono>{node.node_id}</Chip>
        <Chip>{node.layer === "BASIC" ? "Khái niệm" : "Vận dụng khái niệm"}</Chip>
      </header>

      <dl className="flex flex-wrap items-end gap-x-10 gap-y-3">
        <div>
          <dt className="text-sm text-slate-600">Điểm hiểu bài M</dt>
          <dd className="text-5xl font-semibold tabular-nums">
            {node.mastery === null ? "–" : formatViDecimal(node.mastery)}
          </dd>
          <dd className="text-sm text-slate-600">
            ngưỡng qua bài {formatViDecimal(node.pass_rule.min_mastery)}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-slate-600">Mức hiểu</dt>
          <dd className="text-xl font-semibold">
            {node.mastery === null
              ? "Chưa có bằng chứng"
              : `${node.level} · ${LEVEL_LABEL[node.level] ?? ""}`}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-slate-600">Độ tin cậy</dt>
          <dd className="text-xl font-semibold tabular-nums">
            {formatViDecimal(node.confidence)}
            {node.insufficient_data && (
              <span className="ml-2 text-sm font-normal text-amber-800">chưa đủ dữ liệu</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-slate-600">Điểm khởi đầu (từ bài tiên quyết)</dt>
          <dd className="text-xl font-semibold tabular-nums">
            {formatViDecimal(Math.round(node.prior * 1000) / 10)}
          </dd>
        </div>
      </dl>

      <MasteryChart points={trace} threshold={node.pass_rule.min_mastery} name={node.name} />
      <DimensionBars node={node} />
      <PassRule node={node} />
      {node.misconceptions.length > 0 && (
        <div>
          <h4 className="mb-2 font-semibold">Lỗi sai đã phát hiện</h4>
          <ul className="flex flex-col gap-1">
            {node.misconceptions.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-2 text-sm">
                <Chip
                  tone={m.status === "RESOLVED" ? "emerald" : m.severity === "CRITICAL" ? "rose" : "amber"}
                  mono
                >
                  {m.id}
                </Chip>
                {m.name} · {m.count} lần ·{" "}
                {m.status === "RESOLVED" ? "đã sửa được" : m.status === "RESOLVING" ? "đang sửa" : "đang mắc"}
                {m.severity === "CRITICAL" && " · nghiêm trọng"}
              </li>
            ))}
          </ul>
        </div>
      )}
      <EvidenceTable evidence={evidence} />
    </section>
  );
}

/** M after every event that changed it, with the pass threshold. One series: the title names it. */
function MasteryChart({
  points,
  threshold,
  name,
}: {
  points: MasteryPoint[];
  threshold: number;
  name: string;
}) {
  const [frame, W] = useElementWidth(600);
  const H = 180;
  const left = 34;
  const right = 16;
  const top = 12;
  const bottom = 22;
  const y = (m: number) => top + (1 - m / 100) * (H - top - bottom);
  const x = (i: number) =>
    points.length < 2 ? left + (W - left - right) / 2 : left + (i * (W - left - right)) / (points.length - 1);
  const last = points.at(-1);
  return (
    <figure ref={frame}>
      <figcaption className="mb-1 font-semibold">Điểm M qua từng lượt</figcaption>
      {points.length === 0 ? (
        <p className="text-sm text-slate-600">Chưa có bằng chứng nào cho bài này.</p>
      ) : (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width={W}
          height={H}
          className="max-w-full"
          role="img"
          aria-label={`Điểm M của bài ${name} qua từng lượt`}
        >
          {[0, 25, 50, 75, 100].map((tick) => (
            <g key={tick}>
              <line
                x1={left}
                x2={W - right}
                y1={y(tick)}
                y2={y(tick)}
                className="stroke-slate-200"
                strokeWidth={1}
              />
              <text
                x={left - 6}
                y={y(tick) + 4}
                textAnchor="end"
                className="fill-slate-500 text-[11px] tabular-nums"
              >
                {tick}
              </text>
            </g>
          ))}
          <line
            x1={left}
            x2={W - right}
            y1={y(threshold)}
            y2={y(threshold)}
            className="stroke-slate-600"
            strokeWidth={1.5}
            strokeDasharray="6 4"
          />
          <text x={W - right} y={y(threshold) - 5} textAnchor="end" className="fill-slate-700 text-[11px]">
            ngưỡng qua bài {formatViDecimal(threshold)}
          </text>
          <polyline
            points={points.map((p, i) => `${x(i)},${y(p.mastery ?? 0)}`).join(" ")}
            fill="none"
            className="stroke-brand-700"
            strokeWidth={2}
            strokeLinejoin="round"
          />
          {points.map((p, i) => (
            <circle
              key={p.sequence_no}
              cx={x(i)}
              cy={y(p.mastery ?? 0)}
              r={4}
              className="fill-brand-700 stroke-white"
              strokeWidth={2}
            >
              <title>{`Lượt #${p.sequence_no} lúc ${formatViTime(p.occurred_at)}: M ${formatViDecimal(p.mastery ?? 0)}`}</title>
            </circle>
          ))}
          {last && (
            <text
              x={x(points.length - 1)}
              y={y(last.mastery ?? 0) - 9}
              textAnchor="end"
              className="fill-slate-900 text-[12px] font-semibold tabular-nums"
            >
              {formatViDecimal(last.mastery ?? 0)}
            </text>
          )}
        </svg>
      )}
    </figure>
  );
}

/** The seven dimensions: mean of each Beta, its weight in M and how much evidence it has (DI-1). */
function DimensionBars({ node }: { node: ReportNode }) {
  return (
    <div>
      <h4 className="mb-2 font-semibold">Bảy chiều đánh giá</h4>
      <ul className="flex flex-col gap-2">
        {DIMENSIONS.map((d) => {
          const dim = node.dimensions[d];
          const percent = Math.round(dim.mean * 100);
          return (
            <li key={d} className="grid grid-cols-[9.5rem_minmax(0,1fr)_10.5rem] items-center gap-3 text-sm">
              <span>
                <span className="font-mono font-semibold">{d}</span> · {DIMENSION_LABEL[d]}{" "}
                <span className="text-slate-500">({Math.round(DIMENSION_WEIGHT[d] * 100)}%)</span>
              </span>
              <span className="h-3 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
                {dim.n_eff > 0 && (
                  <span
                    className={`block h-full rounded-full ${dim.in_mastery ? "bg-brand-600" : "bg-slate-300"}`}
                    style={{ width: `${percent}%` }}
                  />
                )}
              </span>
              <span className="tabular-nums text-slate-700">
                {dim.n_eff > 0 ? (
                  <>
                    {percent}
                    <span className="text-slate-500">
                      {" "}
                      · {formatViDecimal(Math.round(dim.n_eff * 10) / 10)} bằng chứng
                    </span>
                  </>
                ) : (
                  <span className="text-slate-500">chưa có</span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs text-slate-500">
        Chiều có dưới 1 đơn vị bằng chứng (thanh xám) chưa tính vào M; trọng số còn lại được chuẩn hóa lại
        (DI-1).
      </p>
    </div>
  );
}

function Check({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <span
        aria-hidden="true"
        className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
          ok ? "bg-emerald-600 text-white" : "bg-slate-200 text-slate-600"
        }`}
      >
        {ok ? "✓" : "–"}
      </span>
      <span>
        <span className="sr-only">{ok ? "Đạt: " : "Chưa đạt: "}</span>
        {children}
      </span>
    </li>
  );
}

/** The pass rule (DI-15): what is met, what is missing. */
function PassRule({ node }: { node: ReportNode }) {
  const rule = node.pass_rule;
  return (
    <div>
      <h4 className="mb-2 font-semibold">
        Điều kiện qua bài{" "}
        {node.pass_now ? (
          <Chip tone="emerald">đủ điều kiện</Chip>
        ) : (
          <Chip tone="amber">còn thiếu {node.missing.length}</Chip>
        )}
      </h4>
      <ul className="flex flex-col gap-1.5 text-sm">
        <Check ok={node.mastery !== null && node.mastery >= rule.min_mastery}>
          Điểm M ≥ {formatViDecimal(rule.min_mastery)}
        </Check>
        <Check ok={node.understood}>
          Hiểu bài: {node.successes}/{rule.min_successes} lần tự làm được, {node.levels.length}/
          {rule.min_levels} mức nhận thức ({node.levels.join(", ") || "chưa có"}), {node.forms.length}/
          {rule.min_forms} dạng câu
        </Check>
        <Check ok={node.has_explanation}>Giải thích được bằng lời (μ_R ≥ 0,6)</Check>
        <Check ok={node.has_application}>Làm đúng bài vận dụng</Check>
        <Check ok={!node.missing.includes("MISCONCEPTION")}>Không còn lỗi sai nghiêm trọng</Check>
      </ul>
      {!node.pass_now && node.missing.length > 0 && (
        <p className="mt-2 text-sm text-slate-700">
          Cô đang cần thêm: {node.missing.map((m) => MISSING_LABEL[m] ?? m).join("; ")}.
        </p>
      )}
    </div>
  );
}

/** Every piece of evidence of the node, newest first: the table view of the chart above. */
function EvidenceTable({ evidence }: { evidence: EvidenceEntry[] }) {
  const [all, setAll] = useState(false);
  const rows = [...evidence].reverse();
  const shown = all ? rows : rows.slice(0, SHOWN);
  return (
    <div>
      <h4 className="mb-2 font-semibold">Bằng chứng cộng, trừ điểm ({evidence.length})</h4>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-600">Chưa có.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-600">
              <tr>
                <th className="py-1 pr-3 font-medium">Lượt</th>
                <th className="py-1 pr-3 font-medium">Câu</th>
                <th className="py-1 pr-3 font-medium">Chiều</th>
                <th className="py-1 pr-3 font-medium">Tác động</th>
                <th className="py-1 pr-3 font-medium">Trọng số</th>
                <th className="py-1 font-medium">Vì sao</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {shown.map((e, index) => (
                <tr key={`${e.sequence_no}-${e.dimension}-${index}`}>
                  <td className="py-1 pr-3 font-mono text-xs whitespace-nowrap text-slate-500">
                    #{e.sequence_no}
                    {e.earlier && <span className="ml-1 font-sans">(buổi trước)</span>}
                  </td>
                  <td className="py-1 pr-3 font-mono text-xs whitespace-nowrap">{e.item_id ?? "–"}</td>
                  <td className="py-1 pr-3">
                    <span className="font-mono font-semibold">{e.dimension}</span>{" "}
                    {DIMENSION_LABEL[e.dimension]}
                  </td>
                  <td className="py-1 pr-3">
                    <Impact score={e.score} />
                  </td>
                  <td className="py-1 pr-3 tabular-nums">{formatViDecimal(e.weight)}</td>
                  <td className="py-1">{EVIDENCE_REASON_LABEL[e.reason] ?? e.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rows.length > SHOWN && (
        <button type="button" onClick={() => setAll(!all)} className="mt-2 text-sm text-brand-800 underline">
          {all ? "Thu gọn" : `Xem tất cả ${rows.length}`}
        </button>
      )}
    </div>
  );
}

/** A score of 1 adds all of its weight to alpha (cộng), 0 adds it to beta (trừ); between, a part of each. */
function Impact({ score }: { score: number }) {
  if (score >= 1) return <Chip tone="emerald">+ cộng</Chip>;
  if (score <= 0) return <Chip tone="rose">− trừ</Chip>;
  return <Chip tone="amber">± {formatViDecimal(Math.round(score * 100) / 100)}</Chip>;
}

/** Every decision of the teaching policy, newest first, with the rule that took it (plan v1, 5.4). */
function DecisionTimeline({ decisions, names }: { decisions: DecisionEntry[]; names: Map<string, string> }) {
  const [all, setAll] = useState(false);
  const rows = [...decisions].reverse();
  const shown = all ? rows : rows.slice(0, SHOWN * 2);
  return (
    <section aria-labelledby="decisions-title" className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <h3 id="decisions-title" className="font-semibold">
        Quyết định của cô ({decisions.length})
      </h3>
      <p className="mb-3 text-sm text-slate-600">
        Mỗi bước do một luật tất định chọn; AI chỉ diễn đạt lời nói. Mới nhất ở trên.
      </p>
      <ol className="flex flex-col divide-y divide-slate-100">
        {shown.map((d) => (
          <li key={d.sequence_no} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-3 py-2 text-sm">
            <time dateTime={d.occurred_at} className="pt-0.5 font-mono text-xs text-slate-500">
              {formatViTime(d.occurred_at)}
            </time>
            <div className="flex flex-wrap items-center gap-1.5">
              {d.rule_ids.map((rule) => (
                <Chip key={rule} tone="teal" mono title={RULE_LABEL[rule]}>
                  {rule}
                </Chip>
              ))}
              <span className="font-medium">{TEACH_ACTION_LABEL[d.action]}</span>
              {d.node_id && <span className="text-slate-700">· {names.get(d.node_id) ?? d.node_id}</span>}
              {d.ref && <Chip mono>{d.ref}</Chip>}
              {d.reason_codes.map((code) => (
                <Chip key={code} mono>
                  {code}
                </Chip>
              ))}
            </div>
          </li>
        ))}
      </ol>
      {rows.length > SHOWN * 2 && (
        <button type="button" onClick={() => setAll(!all)} className="mt-2 text-sm text-brand-800 underline">
          {all ? "Thu gọn" : `Xem tất cả ${rows.length}`}
        </button>
      )}
    </section>
  );
}
