/** @vitest-environment node */
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";
import { parse } from "yaml";

import { DEFAULT_LESSON_PATH, sealAssessmentItems } from "./mockLesson.ts";

type Json = Record<string, unknown>;

const raw = parse(readFileSync(DEFAULT_LESSON_PATH, "utf8")) as { items: Json[] };
const sealed = sealAssessmentItems(raw) as { items: Json[] };

describe("sealAssessmentItems", () => {
  it("reduces EXIT items to a whitelist of fields", () => {
    const exitItems = sealed.items.filter((it) => it.purpose === "EXIT");
    expect(exitItems.map((it) => it.id)).toEqual([
      "EX-01",
      "EX-02",
      "EX-03",
      "EX-04",
      "EX-05",
      "EX-06",
      "EX-07",
      "EX-08",
    ]);
    for (const item of exitItems) {
      expect(Object.keys(item).sort()).toEqual(
        ["answer", "cognitive_level", "difficulty", "hints", "id", "kc_ids", "purpose", "stem"].sort(),
      );
    }
  });

  it("keeps only the answer type, plus choice labels without correctness", () => {
    const answerOf = (id: string) => sealed.items.find((it) => it.id === id)?.answer;
    expect(answerOf("EX-01")).toEqual({ type: "compare" });
    expect(answerOf("EX-02")).toEqual({ type: "open" });
    expect(answerOf("EX-04")).toEqual({ type: "boolean" });
    expect(answerOf("EX-03")).toEqual({
      type: "choice",
      options: [
        { id: "A", text: "Minh" },
        { id: "B", text: "Nam" },
      ],
    });
  });

  it("drops hints above H1 from EXIT items (R-ASSESS-CAP)", () => {
    const lesson = {
      items: [
        {
          id: "EX-X",
          purpose: "EXIT",
          stem: "s",
          answer: { type: "numeric", value: "6" },
          hints: [
            { target: "TASK", level: 1, text: "h1" },
            { target: "STEP", level: 4, text: "h4 gives it away" },
          ],
        },
      ],
    };
    const [item] = sealAssessmentItems(lesson).items as Json[];
    expect(item.hints).toEqual([{ target: "TASK", level: 1, text: "h1" }]);
    expect(item.answer).toEqual({ type: "numeric" });
  });

  it("leaves every other item unchanged", () => {
    const others = sealed.items.filter((it) => it.purpose !== "EXIT");
    expect(others).toEqual(raw.items.filter((it) => it.purpose !== "EXIT"));
  });

  it("rejects input that is not a lesson package", () => {
    expect(() => sealAssessmentItems(null)).toThrow();
    expect(() => sealAssessmentItems({ items: "x" })).toThrow();
  });
});
