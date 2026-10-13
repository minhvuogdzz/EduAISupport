import type { JourneyStep, TeacherNodeDetail } from "../../../api/contract";
import { RESOLUTION_LABEL } from "../../../components/labels";

const TONE: Record<JourneyStep["resolution"], string> = {
  INDEPENDENT: "bg-emerald-600",
  SUPPORTED: "bg-sky-400",
  WORKED: "bg-amber-400",
  UNRESOLVED: "bg-rose-500",
};

const MARK: Record<JourneyStep["resolution"], string> = {
  INDEPENDENT: "✓",
  SUPPORTED: "g",
  WORKED: "m",
  UNRESOLVED: "✗",
};

function cellTitle(step: JourneyStep, index: number): string {
  const hints = step.hints ? `, ${step.hints} gợi ý` : "";
  return `Câu ${index + 1} (${step.item_id}): ${RESOLUTION_LABEL[step.resolution]}, ${step.attempts} lần trả lời${hints}`;
}

/**
 * The learning heatmap of one student: one row per period, one cell per item in the order the student met
 * it, coloured by how it ended (on their own, with hints, after the worked steps, not solved). A row going
 * from red and amber to green is a period learned in front of the tutor. Each cell has a mark and a tooltip:
 * colour is never the only cue.
 */
export function JourneyHeatmap({ steps, nodes }: { steps: JourneyStep[]; nodes: TeacherNodeDetail[] }) {
  if (steps.length === 0) return <p className="text-slate-600">Chưa có câu nào.</p>;
  const rows = nodes
    .map((n) => ({ node: n, cells: steps.filter((s) => s.node_id === n.node_id) }))
    .filter((r) => r.cells.length > 0);
  return (
    <figure className="flex flex-col gap-3">
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-1 text-sm">
          <tbody>
            {rows.map(({ node, cells }) => (
              <tr key={node.node_id}>
                <th scope="row" className="pr-2 text-left font-medium whitespace-nowrap text-slate-700">
                  <span className="inline-block max-w-56 truncate align-middle" title={node.name}>
                    {node.name}
                  </span>
                </th>
                {cells.map((step, i) => (
                  <td key={`${step.item_id}-${i}`} className="p-0">
                    <span
                      title={cellTitle(step, i)}
                      aria-label={cellTitle(step, i)}
                      className={`flex size-6 items-center justify-center rounded text-[11px] font-bold text-white ${TONE[step.resolution]}`}
                    >
                      {MARK[step.resolution]}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <figcaption className="flex flex-wrap gap-3 text-sm text-slate-700">
        {(Object.keys(TONE) as JourneyStep["resolution"][]).map((r) => (
          <span key={r} className="flex items-center gap-1">
            <span
              className={`flex size-4 items-center justify-center rounded text-[9px] text-white ${TONE[r]}`}
            >
              {MARK[r]}
            </span>
            {RESOLUTION_LABEL[r]} ({steps.filter((s) => s.resolution === r).length})
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
