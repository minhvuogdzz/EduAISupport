import { DIMENSIONS, type TeacherNodeDetail } from "../../../api/contract";
import {
  DIMENSION_LABEL,
  DIRECTION_LABEL,
  KC_GROUP_LABEL,
  KC_GROUP_MARK,
  LEVEL_NAME,
  NODE_STATUS_LABEL,
  RECOMMENDATION_LABEL,
} from "../../../components/labels";
import { formatViDecimal } from "../../../lib/viNumber";
import { ConfidenceBar } from "./MasteryGauge";
import { zoneOf } from "./zones";
import { Method } from "./Method";

const GROUP_TONE: Record<TeacherNodeDetail["group"], string> = {
  PASSED: "bg-emerald-50 text-emerald-900 ring-emerald-200",
  UNSTABLE: "bg-yellow-50 text-yellow-900 ring-yellow-300",
  WEAK: "bg-rose-50 text-rose-900 ring-rose-200",
  INSUFFICIENT: "bg-slate-100 text-slate-700 ring-slate-300",
  NOT_STARTED: "bg-slate-50 text-slate-600 ring-slate-200",
};

const MIS_STATUS: Record<string, string> = {
  ACTIVE: "đang mắc",
  RESOLVING: "đang sửa",
  RESOLVED: "đã sửa được",
};

/**
 * The detail screen of one KC (khung Toán §57): M and confidence as bars, the state, the dimensions, the
 * counts of items, attempts, hints and time, the misconceptions, the trend (§27) and the next move (DI-8).
 */
export function KcDetail({ node }: { node: TeacherNodeDetail }) {
  const titleId = `kc-${node.node_id}`;
  const last = node.trend.slice(-6).map((p) => formatViDecimal(p.mastery));
  return (
    <section aria-labelledby={titleId} className="card flex flex-col gap-5 p-5">
      <header className="flex flex-wrap items-center gap-2">
        <h3 id={titleId} className="text-xl font-bold">
          {node.name}
        </h3>
        <span className={`rounded-full px-2.5 py-0.5 text-sm font-semibold ring-1 ${GROUP_TONE[node.group]}`}>
          {KC_GROUP_MARK[node.group]} {KC_GROUP_LABEL[node.group]}
        </span>
        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-sm text-slate-700">
          {NODE_STATUS_LABEL[node.status]}
        </span>
        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 font-mono text-xs text-slate-600">
          {node.node_id}
        </span>
      </header>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <div className="flex items-baseline justify-between text-sm">
            <span className="text-slate-600">Điểm hiểu bài M</span>
            <span className="text-2xl font-bold tabular-nums">
              {node.mastery === null ? "–" : formatViDecimal(node.mastery)}
            </span>
          </div>
          <div
            className="relative mt-1 h-3 rounded-full bg-slate-100"
            role="img"
            aria-label={
              node.mastery === null
                ? "Chưa có bằng chứng"
                : `M ${formatViDecimal(node.mastery)}, ngưỡng qua bài ${formatViDecimal(node.min_mastery)}`
            }
          >
            {node.mastery !== null && (
              <div
                className={`h-3 rounded-full ${zoneOf(node.mastery).cell}`}
                style={{ width: `${node.mastery}%` }}
              />
            )}
            <span
              aria-hidden="true"
              className="absolute -top-1 h-5 w-0.5 rounded bg-slate-700"
              style={{ left: `${node.min_mastery}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Vạch đứng: ngưỡng qua bài {formatViDecimal(node.min_mastery)} (DI-15)
          </p>
          <p className="mt-2 font-semibold">
            {node.mastery === null ? "Chưa có bằng chứng" : `Mức ${node.level} · ${LEVEL_NAME[node.level]}`}
            {node.mastery !== null && (
              <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs font-normal">
                {node.state}
              </span>
            )}
          </p>
        </div>
        <ConfidenceBar confidence={node.confidence} />
      </div>

      <div>
        <h4 className="mb-2 font-semibold">Các chiều đánh giá</h4>
        <ul className="flex flex-col gap-1.5">
          {DIMENSIONS.map((d) => {
            const dim = node.dimensions[d];
            return (
              <li key={d} className="grid grid-cols-[8.5rem_1fr_7.5rem] items-center gap-3 text-sm">
                <span>
                  <span className="font-mono text-slate-500">{d}</span> · {DIMENSION_LABEL[d]}
                </span>
                <span className="h-2 rounded-full bg-slate-100">
                  {dim.n_eff > 0 && (
                    <span
                      className={`block h-2 rounded-full ${dim.in_mastery ? "bg-brand-500" : "bg-slate-300"}`}
                      style={{ width: `${dim.value}%` }}
                    />
                  )}
                </span>
                <span className="text-right text-slate-600 tabular-nums">
                  {dim.n_eff > 0
                    ? `${formatViDecimal(dim.value)}${dim.in_mastery ? "" : " · chưa tính"}`
                    : "chưa có"}
                </span>
              </li>
            );
          })}
        </ul>
        <Method>
          Chiều có dưới 1 đơn vị bằng chứng chưa tính vào M (DI-1); thanh xám là chiều chưa tính.
        </Method>
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {[
          ["Số câu", String(node.items)],
          ["Giải được", String(node.solved)],
          ["Lần trả lời", String(node.attempts)],
          ["Gợi ý", String(node.hints)],
          ["TB mỗi câu", node.seconds === null ? "–" : `${node.seconds} giây`],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl bg-slate-50 px-3 py-2">
            <dt className="text-xs text-slate-600">{label}</dt>
            <dd className="text-lg font-bold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>

      {node.misconceptions.length > 0 && (
        <div>
          <h4 className="mb-2 font-semibold">Lỗi sai</h4>
          <ul className="flex flex-col gap-1.5 text-sm">
            {node.misconceptions.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-2">
                <span
                  aria-hidden="true"
                  className={m.status === "RESOLVED" ? "text-emerald-600" : "text-rose-600"}
                >
                  {m.status === "RESOLVED" ? "✓" : "⚠"}
                </span>
                <span className="font-medium">{m.name}</span>
                <span className="text-slate-600">
                  {m.count} lần · {MIS_STATUS[m.status] ?? m.status}
                  {m.severity === "CRITICAL" ? " · nghiêm trọng" : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <h4 className="mb-1 font-semibold">Xu hướng</h4>
          {node.trend.length === 0 ? (
            <p className="text-sm text-slate-600">Chưa có điểm.</p>
          ) : (
            <p className="text-sm">
              <span className="tabular-nums">{last.join(" → ")}</span>
              {node.direction && (
                <span className="ml-2 font-semibold">{DIRECTION_LABEL[node.direction]}</span>
              )}
            </p>
          )}
          <p className="mt-1 text-xs text-slate-500">So với điểm 3 lần đổi trước, chênh từ 3 điểm (DI-24)</p>
        </div>
        <div>
          <h4 className="mb-1 font-semibold">Khuyến nghị</h4>
          <p className="text-sm">{RECOMMENDATION_LABEL[node.recommendation]}</p>
          <p className="mt-1 text-xs text-slate-500">Theo dải điểm M (DI-8, chờ duyệt)</p>
        </div>
      </div>
    </section>
  );
}
