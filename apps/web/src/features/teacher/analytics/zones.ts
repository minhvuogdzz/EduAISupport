/**
 * The colour zones of M (khung Toán §25): 90–100 dark green, 75–89 green, 60–74 yellow, 40–59 orange,
 * 0–39 red. Levels 0 and 1 share the red zone (blueprint 26.1). Every coloured mark also carries its
 * number or its words: colour is never the only cue.
 */
export interface Zone {
  from: number;
  range: string;
  name: string;
  /** Background and text of a table cell or a chip. */
  cell: string;
  /** SVG fill and stroke. */
  fill: string;
  stroke: string;
}

export const ZONES: readonly Zone[] = [
  {
    from: 90,
    range: "90–100",
    name: "xanh đậm",
    cell: "bg-emerald-700 text-white",
    fill: "fill-emerald-700",
    stroke: "stroke-emerald-700",
  },
  {
    from: 75,
    range: "75–89",
    name: "xanh",
    cell: "bg-emerald-300 text-emerald-950",
    fill: "fill-emerald-300",
    stroke: "stroke-emerald-400",
  },
  {
    from: 60,
    range: "60–74",
    name: "vàng",
    cell: "bg-yellow-300 text-yellow-950",
    fill: "fill-yellow-300",
    stroke: "stroke-yellow-400",
  },
  {
    from: 40,
    range: "40–59",
    name: "cam",
    cell: "bg-orange-400 text-orange-950",
    fill: "fill-orange-400",
    stroke: "stroke-orange-500",
  },
  {
    from: 0,
    range: "0–39",
    name: "đỏ",
    cell: "bg-red-600 text-white",
    fill: "fill-red-600",
    stroke: "stroke-red-600",
  },
];

/** The zone of a value of M (0–100). */
export function zoneOf(mastery: number): Zone {
  return ZONES.find((zone) => mastery >= zone.from) ?? ZONES[ZONES.length - 1];
}

/** M as a whole number for a cell: rounded down, so the number always lies in its zone's range. */
export function cellNumber(mastery: number): string {
  return String(Math.floor(mastery));
}

/** DI-7: below this confidence the number stays visible to the teacher, with a warning (PART 27.3). */
export const CONFIDENCE_FLOOR = 30;
