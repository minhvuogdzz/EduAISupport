import { useState } from "react";
import { Link } from "react-router";

import type { ClassOverview, ClassStudent, MasteryCell, TeacherNode } from "../../../api/contract";
import { AlertIcon } from "../../../components/icons";
import { formatViDecimal } from "../../../lib/viNumber";
import { columns } from "./helpers";
import { cellNumber, ZONES, zoneOf } from "./zones";

type Order = "name" | "low" | "attention";

const ORDER_LABEL: Record<Order, string> = {
  name: "Theo tên",
  low: "Điểm thấp trước",
  attention: "Cần chú ý trước",
};

function sorted(students: ClassStudent[], order: Order): ClassStudent[] {
  const low = (s: ClassStudent) => s.overall.mastery ?? Number.POSITIVE_INFINITY;
  if (order === "low") return [...students].sort((a, b) => low(a) - low(b));
  if (order === "attention") return [...students].sort((a, b) => b.attention.length - a.attention.length);
  return students;
}

/** What a cell says, for its tooltip and for screen readers. */
function cellText(student: string, node: string, cell: MasteryCell): string {
  if (cell.mastery === null) return `${student}, ${node}: chưa có bằng chứng`;
  const parts = [
    `M ${formatViDecimal(cell.mastery)}`,
    `độ tin cậy ${formatViDecimal(cell.confidence)}`,
    cell.insufficient_data ? "chưa đủ dữ liệu" : null,
    cell.passed ? "đã qua bài" : null,
    cell.active_misconceptions ? `${cell.active_misconceptions} lỗi đang mắc` : null,
  ];
  return `${student}, ${node}: ${parts.filter(Boolean).join(", ")}`;
}

/**
 * The Student × Knowledge matrix (khung Toán §46) as a heatmap in the zones of §25, with the class row
 * of §45 at the bottom. Each cell opens the student's report on that KC. A cell below the confidence
 * floor of DI-7 keeps its number but is hatched and marked "?".
 */
export function Heatmap({ overview }: { overview: ClassOverview }) {
  const [order, setOrder] = useState<Order>("name");
  const cols = columns(overview.nodes);
  const basic = cols.filter((n) => n.layer === "BASIC").length;
  const byNode = new Map(overview.by_node.map((b) => [b.node_id, b]));
  return (
    <div className="flex flex-col gap-3">
      <div role="group" aria-label="Sắp xếp học sinh" className="flex flex-wrap gap-2">
        {(Object.keys(ORDER_LABEL) as Order[]).map((key) => (
          <button
            key={key}
            type="button"
            aria-pressed={order === key}
            onClick={() => setOrder(key)}
            className={`rounded-full px-3 py-1 text-sm font-medium ${
              order === key ? "bg-brand-700 text-white" : "bg-white text-slate-700 ring-1 ring-slate-300"
            }`}
          >
            {ORDER_LABEL[key]}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] border-separate border-spacing-1 text-sm">
          <caption className="sr-only">
            Bản đồ nhiệt học sinh và bài: điểm M từng bài, tô màu theo vùng của khung Toán mục 25
          </caption>
          <thead>
            <tr className="text-xs tracking-wide text-slate-500 uppercase">
              <th scope="col" rowSpan={2} className="w-40 px-2 text-left align-bottom font-semibold">
                Học sinh
              </th>
              <th scope="colgroup" colSpan={basic} className="border-b border-slate-200 pb-1 font-semibold">
                Khái niệm
              </th>
              {cols.length > basic && (
                <th
                  scope="colgroup"
                  colSpan={cols.length - basic}
                  className="border-b border-slate-200 pb-1 font-semibold"
                >
                  Vận dụng khái niệm
                </th>
              )}
              <th scope="col" rowSpan={2} className="w-24 px-1 align-bottom font-semibold">
                Tổng (§23)
              </th>
            </tr>
            <tr>
              {cols.map((n) => (
                <th
                  key={n.node_id}
                  scope="col"
                  className="px-1 align-bottom text-xs leading-tight font-medium text-slate-700"
                >
                  <span className="line-clamp-3" title={n.name}>
                    {n.name}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted(overview.students, order).map((s) => {
              const cells = new Map(s.cells.map((c) => [c.node_id, c]));
              return (
                <tr key={s.student_id}>
                  <th scope="row" className="px-2 text-left font-normal">
                    <Link
                      to={`/teacher/students/${encodeURIComponent(s.student_id)}`}
                      className="inline-flex items-center gap-1.5 font-semibold text-brand-900 hover:underline"
                    >
                      {s.display_name}
                      {s.attention.length > 0 && (
                        <>
                          <AlertIcon className="size-4 text-rose-600" />
                          <span className="sr-only"> (cần chú ý)</span>
                        </>
                      )}
                    </Link>
                    <span className="block text-xs text-slate-500">
                      {s.passed}/{cols.length} bài · {s.sessions.total} buổi
                    </span>
                  </th>
                  {cols.map((n) => {
                    const cell = cells.get(n.node_id);
                    return (
                      <td key={n.node_id} className="p-0">
                        {cell && <Cell student={s} node={n} cell={cell} />}
                      </td>
                    );
                  })}
                  <td className="p-0">
                    <Overall mastery={s.overall.mastery} coverage={s.overall.coverage} />
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="px-2 pt-2 text-left text-xs font-semibold text-slate-600">
                Cả lớp (§45)
              </th>
              {cols.map((n) => {
                const b = byNode.get(n.node_id);
                const mean = b?.mean_mastery ?? null;
                return (
                  <td key={n.node_id} className="p-0 pt-2">
                    <div
                      title={
                        mean === null
                          ? `${n.name}: chưa em nào có điểm`
                          : `${n.name}: trung bình M ${formatViDecimal(mean)} của ${b?.students} em, ${b?.passed} em qua bài`
                      }
                      className={`flex h-11 flex-col items-center justify-center rounded-lg border-2 border-white text-xs font-semibold tabular-nums ring-1 ring-slate-300 ${
                        mean === null ? "bg-slate-50 text-slate-400" : zoneOf(mean).cell
                      }`}
                    >
                      <span className="text-sm">{mean === null ? "–" : cellNumber(mean)}</span>
                      <span className="font-normal opacity-90">{b?.students ?? 0} em</span>
                    </div>
                  </td>
                );
              })}
              <td className="p-0 pt-2" />
            </tr>
          </tfoot>
        </table>
      </div>
      <ZoneLegend />
    </div>
  );
}

function Cell({ student, node, cell }: { student: ClassStudent; node: TeacherNode; cell: MasteryCell }) {
  const text = cellText(student.display_name, node.name, cell);
  const tone = cell.mastery === null ? "bg-slate-100 text-slate-400" : zoneOf(cell.mastery).cell;
  return (
    <Link
      to={`/teacher/students/${encodeURIComponent(student.student_id)}?node=${encodeURIComponent(node.node_id)}`}
      aria-label={text}
      title={text}
      className={`relative flex h-12 min-w-12 items-center justify-center rounded-lg text-base font-bold tabular-nums hover:ring-2 hover:ring-sky-500 ${tone} ${
        cell.mastery !== null && cell.insufficient_data ? "hatched" : ""
      }`}
    >
      {cell.mastery === null ? "–" : cellNumber(cell.mastery)}
      {cell.mastery !== null && cell.insufficient_data && (
        <span aria-hidden="true" className="absolute top-0.5 left-1 text-[10px] font-bold">
          ?
        </span>
      )}
      {cell.passed && (
        <span aria-hidden="true" className="absolute top-0.5 right-1 text-[11px] leading-none">
          ✓
        </span>
      )}
      {cell.active_misconceptions > 0 && (
        <span
          aria-hidden="true"
          className="absolute -right-1 -bottom-1 flex size-4 items-center justify-center rounded-full bg-rose-600 text-[10px] font-bold text-white ring-2 ring-white"
        >
          !
        </span>
      )}
    </Link>
  );
}

function Overall({ mastery, coverage }: { mastery: number | null; coverage: number }) {
  return (
    <div
      className={`flex h-12 flex-col items-center justify-center rounded-lg ring-1 ring-slate-300 ${
        mastery === null ? "bg-white text-slate-400" : zoneOf(mastery).cell
      }`}
      title={
        mastery === null
          ? "Chưa có bài nào đủ bằng chứng"
          : `Điểm tổng ${formatViDecimal(mastery)} trên ${formatViDecimal(coverage)}% số bài có điểm`
      }
    >
      <span className="text-base font-bold tabular-nums">{mastery === null ? "–" : cellNumber(mastery)}</span>
      <span className="text-[11px] opacity-90">phủ {formatViDecimal(Math.round(coverage))}%</span>
    </div>
  );
}

/** The colour convention of §25 and the marks used on top of it. */
export function ZoneLegend() {
  return (
    <ul
      className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-700"
      aria-label="Chú giải màu"
    >
      {ZONES.map((z) => (
        <li key={z.range} className="flex items-center gap-1.5">
          <span aria-hidden="true" className={`inline-block h-4 w-6 rounded ${z.cell}`} />
          {z.range} ({z.name})
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <span aria-hidden="true" className="inline-block h-4 w-6 rounded bg-slate-100" /> chưa có bằng chứng
      </li>
      <li className="flex items-center gap-1.5">
        <span aria-hidden="true" className="hatched inline-block h-4 w-6 rounded bg-yellow-300" />? độ tin cậy
        dưới 30, chưa đủ dữ liệu (DI-7)
      </li>
      <li>✓ đã qua bài (DI-15)</li>
      <li className="flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className="flex size-4 items-center justify-center rounded-full bg-rose-600 text-[10px] font-bold text-white"
        >
          !
        </span>
        đang mắc lỗi
      </li>
    </ul>
  );
}
