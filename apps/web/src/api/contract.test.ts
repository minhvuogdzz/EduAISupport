import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  ACTIVITY_TYPES,
  ERROR_CLASSES,
  HINT_MOVES,
  HINT_TARGETS,
  ITEM_RESOLUTIONS,
  MOVES,
  OUTCOMES,
  TEACH_ACTIONS,
} from "./contract";

const PEDAGOGY_PY = resolve(import.meta.dirname, "../../../../services/api/cavat/core/pedagogy.py");
const pedagogyPy = readFileSync(PEDAGOGY_PY, "utf8");

/** Values of a `class X(StrEnum)` / `class X(IntEnum)` block in pedagogy.py, in declaration order. */
function enumValues(className: string): string[] {
  const start = pedagogyPy.indexOf(`class ${className}(`);
  if (start < 0) throw new Error(`class ${className} not found in pedagogy.py`);
  const values: string[] = [];
  for (const line of pedagogyPy.slice(start).split("\n").slice(1)) {
    if (/^\S/.test(line)) break; // dedent: the class body ended
    const member = /^\s+[A-Z][A-Z0-9_]*\s*=\s*("?)([A-Z0-9_]+)\1\s*(#.*)?$/.exec(line);
    if (member) values.push(member[2]);
  }
  return values;
}

describe("contract enums mirror services/api/cavat/core/pedagogy.py", () => {
  it.each([
    ["Move", MOVES],
    ["HintTarget", HINT_TARGETS],
    ["Outcome", OUTCOMES],
    ["ErrorClass", ERROR_CLASSES],
    ["ActivityType", ACTIVITY_TYPES],
    ["ItemResolution", ITEM_RESOLUTIONS],
    ["TeachAction", TEACH_ACTIONS],
  ])("%s", (className, values) => {
    expect(values).toEqual(enumValues(className));
  });

  it("HintLevel is the integer ladder 0..7", () => {
    expect(enumValues("HintLevel")).toEqual(["0", "1", "2", "3", "4", "5", "6", "7"]);
  });

  it("HINT_MOVES", () => {
    const block = /HINT_MOVES = frozenset\(\{([^}]*)\}\)/.exec(pedagogyPy);
    const pyMoves = [...(block?.[1] ?? "").matchAll(/Move\.([A-Z_]+)/g)].map((m) => m[1]);
    expect([...HINT_MOVES].sort()).toEqual(pyMoves.sort());
  });
});
