import { useId, type KeyboardEvent } from "react";

import type { KnowledgeRelation, NodeLayer, NodeStatus } from "../../api/contract";
import { LEVEL_LABEL, NODE_STATUS_LABEL } from "../../components/labels";
import { formatViDecimal } from "../../lib/viNumber";

/** A node as the map draws it. The student map shows a level in words; the teacher map shows M. */
export interface MapNode {
  node_id: string;
  name: string;
  layer: NodeLayer;
  status: NodeStatus;
  level: number | null;
  mastery?: number | null;
}

interface KnowledgeMapProps {
  /** In learning order: one row each, so prerequisites are always above. */
  nodes: MapNode[];
  relations: KnowledgeRelation[];
  title: string;
  showMastery?: boolean;
  /** An SVG fill class per node, drawn as a strip on the box (the zones of M, khung Toán §26). */
  zoneFill?: (node: MapNode) => string | null;
  selectedId?: string | null;
  onSelect?: (nodeId: string) => void;
}

const BOX_W = 196;
const BOX_H = 66;
const ROW = 86;
const TOP = 30;
const COL_X: Record<NodeLayer, number> = { BASIC: 30, IMPLEMENT: 266 };
const WIDTH = COL_X.IMPLEMENT + BOX_W + 30;
const LINE_CHARS = 21;

const COLUMN_LABEL: Record<NodeLayer, string> = { BASIC: "Khái niệm", IMPLEMENT: "Vận dụng khái niệm" };

/** Fill, border and text of a node box per status. Status is never shown by color alone. */
const STYLE: Record<NodeStatus, { box: string; text: string; sub: string; glyph: string }> = {
  PASSED: {
    box: "fill-emerald-50 stroke-emerald-600",
    text: "fill-emerald-950",
    sub: "fill-emerald-800",
    glyph: "text-emerald-700",
  },
  CURRENT: {
    box: "fill-brand-700 stroke-brand-700",
    text: "fill-white",
    sub: "fill-brand-50",
    glyph: "text-white",
  },
  ON_HOLD: {
    box: "fill-amber-50 stroke-amber-500",
    text: "fill-amber-950",
    sub: "fill-amber-800",
    glyph: "text-amber-700",
  },
  STOPPED: {
    box: "fill-rose-50 stroke-rose-500",
    text: "fill-rose-950",
    sub: "fill-rose-800",
    glyph: "text-rose-700",
  },
  AVAILABLE: {
    box: "fill-white stroke-slate-400",
    text: "fill-slate-900",
    sub: "fill-slate-600",
    glyph: "text-slate-500",
  },
  LOCKED: {
    box: "fill-slate-100 stroke-slate-300",
    text: "fill-slate-500",
    sub: "fill-slate-500",
    glyph: "text-slate-400",
  },
};

interface Box {
  x: number;
  y: number;
}

/** Two lines at most, cut on words; a longer name ends with "…". */
function wrap(name: string): [string, string] {
  const words = name.split(" ");
  let first = "";
  let index = 0;
  while (index < words.length && `${first} ${words[index]}`.trim().length <= LINE_CHARS) {
    first = `${first} ${words[index]}`.trim();
    index += 1;
  }
  let second = words.slice(index).join(" ");
  if (second.length > LINE_CHARS) second = `${second.slice(0, LINE_CHARS - 1).trimEnd()}…`;
  return [first, second];
}

/** Edges: down a column between neighbours, a bend on the outer side when rows are skipped, a curve across. */
function edgePath(s: Box, t: Box): string {
  if (s.x === t.x) {
    const cx = s.x + BOX_W / 2;
    if (t.y - s.y === ROW) return `M ${cx} ${s.y + BOX_H} L ${cx} ${t.y}`;
    const left = s.x === COL_X.BASIC;
    const side = left ? s.x : s.x + BOX_W;
    const out = left ? -24 : 24;
    const sy = s.y + BOX_H / 2;
    const ty = t.y + BOX_H / 2;
    return `M ${side} ${sy} C ${side + out} ${sy}, ${side + out} ${ty}, ${side} ${ty}`;
  }
  const rightward = t.x > s.x;
  const sx = rightward ? s.x + BOX_W : s.x;
  const tx = rightward ? t.x : t.x + BOX_W;
  const sy = s.y + BOX_H / 2;
  const ty = t.y + BOX_H / 2;
  const bend = rightward ? 36 : -36;
  return `M ${sx} ${sy} C ${sx + bend} ${sy}, ${tx - bend} ${ty}, ${tx} ${ty}`;
}

function StatusGlyph({ status }: { status: NodeStatus }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" } as const;
  switch (status) {
    case "PASSED":
      return <polyline points="2,7 5,10 11,3" {...common} />;
    case "CURRENT":
      return <polygon points="3,2 11,6.5 3,11" fill="currentColor" />;
    case "ON_HOLD":
      return (
        <g fill="currentColor">
          <rect x="3" y="2" width="2.5" height="9" rx="1" />
          <rect x="8" y="2" width="2.5" height="9" rx="1" />
        </g>
      );
    case "STOPPED":
      return (
        <g {...common}>
          <line x1="6.5" y1="2" x2="6.5" y2="8" />
          <line x1="6.5" y1="11" x2="6.5" y2="11.2" />
        </g>
      );
    case "AVAILABLE":
      return <circle cx="6.5" cy="6.5" r="4.5" {...common} />;
    case "LOCKED":
      return (
        <g {...common}>
          <rect x="2.5" y="6" width="8" height="6" rx="1.5" />
          <path d="M4.5 6 V4.5 a2 2 0 0 1 4 0 V6" />
        </g>
      );
  }
}

/**
 * The chapter's knowledge graph (plan v1, 5.1): concepts on the left, the operations that apply them on
 * the right, one row per node in learning order. Solid arrows: "học trước" (prerequisite); dashed
 * arrows: "áp dụng vào" (application). A list below the drawing says the same for screen readers.
 */
export function KnowledgeMap({
  nodes,
  relations,
  title,
  showMastery,
  zoneFill,
  selectedId,
  onSelect,
}: KnowledgeMapProps) {
  const uid = useId().replace(/:/g, "");
  const boxes = new Map(
    nodes.map((node, row) => [node.node_id, { x: COL_X[node.layer], y: TOP + row * ROW }]),
  );
  const current = nodes.find((n) => n.status === "CURRENT")?.node_id ?? null;
  const height = TOP + nodes.length * ROW;

  function detail(node: MapNode): string {
    if (showMastery) {
      return node.mastery === null || node.mastery === undefined
        ? "chưa có điểm"
        : `M ${formatViDecimal(node.mastery)}`;
    }
    return node.level === null ? "" : (LEVEL_LABEL[node.level] ?? "");
  }

  function onKey(event: KeyboardEvent<SVGGElement>, nodeId: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect?.(nodeId);
    }
  }

  return (
    <figure className="flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        className="h-auto w-full"
        role="group"
        aria-labelledby={`${uid}-title`}
      >
        <title id={`${uid}-title`}>{title}</title>
        <defs>
          <marker
            id={`${uid}-arrow`}
            viewBox="0 0 8 8"
            refX="7"
            refY="4"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L8 4 L0 8 z" className="fill-slate-400" />
          </marker>
          <marker
            id={`${uid}-arrow-hot`}
            viewBox="0 0 8 8"
            refX="7"
            refY="4"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L8 4 L0 8 z" className="fill-brand-700" />
          </marker>
        </defs>
        {(["BASIC", "IMPLEMENT"] as const).map((layer) => (
          <text
            key={layer}
            x={COL_X[layer] + BOX_W / 2}
            y={16}
            textAnchor="middle"
            className="fill-slate-500 text-[12px] font-semibold tracking-wide uppercase"
          >
            {COLUMN_LABEL[layer]}
          </text>
        ))}
        {relations.map((r) => {
          const s = boxes.get(r.source);
          const t = boxes.get(r.target);
          if (!s || !t) return null;
          const hot = r.target === current;
          return (
            <path
              key={`${r.source}-${r.type}-${r.target}`}
              d={edgePath(s, t)}
              fill="none"
              strokeWidth={hot ? 2 : 1.5}
              strokeDasharray={r.type === "APPLICATION" ? "5 4" : undefined}
              markerEnd={`url(#${uid}-${hot ? "arrow-hot" : "arrow"})`}
              className={hot ? "stroke-brand-700" : "stroke-slate-400"}
            />
          );
        })}
        {nodes.map((node) => {
          const box = boxes.get(node.node_id);
          if (!box) return null;
          const style = STYLE[node.status];
          const [line1, line2] = wrap(node.name);
          const selected = node.node_id === selectedId;
          const label = `${node.name}: ${NODE_STATUS_LABEL[node.status]}${detail(node) ? `, ${detail(node)}` : ""}`;
          return (
            <g
              key={node.node_id}
              transform={`translate(${box.x} ${box.y})`}
              role={onSelect ? "button" : undefined}
              tabIndex={onSelect ? 0 : undefined}
              aria-label={onSelect ? label : undefined}
              aria-pressed={onSelect ? selected : undefined}
              onClick={onSelect ? () => onSelect(node.node_id) : undefined}
              onKeyDown={onSelect ? (event) => onKey(event, node.node_id) : undefined}
              className={onSelect ? "cursor-pointer" : undefined}
            >
              {selected && (
                <rect
                  x={-5}
                  y={-5}
                  width={BOX_W + 10}
                  height={BOX_H + 10}
                  rx={18}
                  className="fill-none stroke-sky-500"
                  strokeWidth={3}
                />
              )}
              <rect width={BOX_W} height={BOX_H} rx={14} strokeWidth={2} className={style.box} />
              {zoneFill?.(node) && (
                <rect
                  x={BOX_W - 11}
                  y={9}
                  width={6}
                  height={BOX_H - 18}
                  rx={3}
                  className={zoneFill(node) ?? undefined}
                />
              )}
              {node.status === "CURRENT" && (
                <rect
                  x={-3}
                  y={-3}
                  width={BOX_W + 6}
                  height={BOX_H + 6}
                  rx={16}
                  className="fill-none stroke-brand-400 motion-safe:animate-pulse"
                  strokeWidth={2}
                />
              )}
              <text x={14} y={line2 ? 22 : 29} className={`${style.text} text-[15px] font-semibold`}>
                {line1}
              </text>
              {line2 && (
                <text x={14} y={40} className={`${style.text} text-[15px] font-semibold`}>
                  {line2}
                </text>
              )}
              <g transform="translate(14 47)">
                <g className={style.glyph}>
                  <StatusGlyph status={node.status} />
                </g>
                <text x={18} y={11} className={`${style.sub} text-[12.5px]`}>
                  {NODE_STATUS_LABEL[node.status]}
                  {detail(node) ? ` · ${detail(node)}` : ""}
                </text>
              </g>
            </g>
          );
        })}
      </svg>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600">
        <span className="inline-flex items-center gap-1.5">
          <svg width="28" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="28" y2="4" className="stroke-slate-400" strokeWidth={1.5} />
          </svg>
          học trước
        </span>
        <span className="inline-flex items-center gap-1.5">
          <svg width="28" height="8" aria-hidden="true">
            <line
              x1="0"
              y1="4"
              x2="28"
              y2="4"
              className="stroke-slate-400"
              strokeWidth={1.5}
              strokeDasharray="5 4"
            />
          </svg>
          áp dụng vào
        </span>
      </figcaption>
      <ul className="sr-only">
        {nodes.map((node) => (
          <li key={node.node_id}>
            {node.name}: {NODE_STATUS_LABEL[node.status]}
            {detail(node) ? `, ${detail(node)}` : ""}
          </li>
        ))}
      </ul>
    </figure>
  );
}
