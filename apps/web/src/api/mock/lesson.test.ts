import { describe, expect, it } from "vitest";

import { LESSON, MOCK_PLAN, PLAN_ITEM_COUNT, lessonItem } from "./lesson";

describe("lesson served to the browser (virtual:cavat/mock-lesson)", () => {
  it("is lesson 1", () => {
    expect(LESSON.lesson_id).toBe("math-g5-dec-compare");
    expect(LESSON.persona).toEqual({ tutor_self: "cô", student_address: "con" });
  });

  it("contains no EXIT answer, solution or rubric (CLAUDE.md rule 2)", () => {
    const exitItems = LESSON.items.filter((it) => it.purpose === "EXIT");
    expect(exitItems.length).toBeGreaterThan(0);
    for (const item of exitItems) {
      const json = JSON.stringify(item);
      for (const secret of [
        '"correct"',
        '"value"',
        '"left"',
        '"right"',
        '"numbers"',
        '"wrong_answers"',
        '"sample_answer"',
        '"rubric"',
        '"worked_solution"',
        '"explanation"',
        '"leak_patterns"',
        '"aliases"',
      ]) {
        expect(json, `${item.id} leaks ${secret}`).not.toContain(secret);
      }
      expect(item.hints.every((h) => h.level <= 1)).toBe(true);
    }
  });

  it("keeps practice items complete so the mock can grade them", () => {
    const gp01 = lessonItem(LESSON, "GP-01");
    expect(gp01.purpose).toBe("PRACTICE");
    expect(gp01.answer).toEqual({ type: "compare", left: "0,25", right: "0,3" });
  });

  it("has every item of the mock plan", () => {
    expect(PLAN_ITEM_COUNT).toBe(8);
    for (const step of MOCK_PLAN) for (const id of step.item_ids) expect(lessonItem(LESSON, id).id).toBe(id);
  });
});
