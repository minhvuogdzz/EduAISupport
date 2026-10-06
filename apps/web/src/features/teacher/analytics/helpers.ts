import type { Dimension, TeacherNode } from "../../../api/contract";

/** Columns grouped by layer (concepts, then their applications), each in learning order. */
export function columns(nodes: TeacherNode[]): TeacherNode[] {
  return [...nodes].sort((a, b) => (a.layer === b.layer ? a.order - b.order : a.layer === "BASIC" ? -1 : 1));
}

/**
 * The six axes of the radar in the order of khung Toán §24: Knowledge, Reasoning, Application, Transfer,
 * Independence, Retention. Knowledge is read from C, correctness (blueprint C1, a declared interpretation);
 * D, error detection, is the seventh dimension of M and is shown beside the radar.
 */
export const RADAR_AXES: readonly Dimension[] = ["C", "R", "A", "T", "I", "S"];

/** DI-28: how urgent the most recurring misconception is, for the callout of §28. */
export function urgency(m: { severity: string; recent: number; active_students: number }): string {
  if (m.active_students === 0) return "Đã sửa được";
  if (m.severity === "CRITICAL" || m.recent >= 3) return "Cần can thiệp";
  return "Theo dõi";
}
