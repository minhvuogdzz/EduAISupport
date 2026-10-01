import { describe, expect, it } from "vitest";

import { checkAnswer, compareDecimals, normalizeVi, parseDecimal } from "./checker";
import { LESSON, lessonItem } from "./lesson";
import type { AnswerSpec } from "./lessonTypes";

function answerOf(itemId: string): AnswerSpec {
  const item = lessonItem(LESSON, itemId);
  if (item.purpose === "EXIT") throw new Error("EXIT items are sealed");
  return item.answer;
}

const compare = (left: string, right: string): AnswerSpec => ({ type: "compare", left, right });

describe("normalizeVi", () => {
  it("drops diacritics and punctuation", () => {
    expect(normalizeVi("  Hoa ạ. ")).toBe("hoa a");
    expect(normalizeVi("Đúng rồi!")).toBe("dung roi");
    expect(normalizeVi("bé hơn")).toBe("be hon");
  });
});

describe("decimals", () => {
  it("compares exactly, comma or dot", () => {
    const d = (s: string) => parseDecimal(s)!;
    expect(compareDecimals(d("0,25"), d("0,3"))).toBe(-1);
    expect(compareDecimals(d("0.50"), d("0,5"))).toBe(0);
    expect(compareDecimals(d("2,1"), d("1,99"))).toBe(1);
    expect(parseDecimal("abc")).toBeNull();
  });
});

describe("compare items", () => {
  const gp01 = answerOf("GP-01"); // 0,25 … 0,3

  it.each([["<"], ["0,25 < 0,3"], ["0.25<0.3"], ["0,3 > 0,25"], ["0,25 bé hơn 0,3"], ["be hon"]])(
    "%j is correct",
    (text) => {
      expect(checkAnswer(gp01, text)).toMatchObject({ outcome: "CORRECT", normalized: "0,25 < 0,3" });
    },
  );

  it.each([[">"], ["0,25 lớn hơn 0,3"], ["0,3 < 0,25"]])("%j is DEC-M01", (text) => {
    expect(checkAnswer(gp01, text)).toMatchObject({
      outcome: "WRONG",
      normalized: "0,25 > 0,3",
      misconception_id: "DEC-M01",
    });
  });

  it.each([
    [compare("0,4", "0,45"), ">", "DEC-M02"],
    [compare("0,05", "0,5"), "=", "DEC-M03"],
    [compare("2,1", "1,99"), "<", "DEC-M04"],
    [compare("0,50", "0,5"), ">", "DEC-M05"],
    [compare("0,7", "0,65"), "<", "DEC-M01"],
    [compare("0,05", "0,5"), ">", "DEC-M01"],
  ])("%j with %j → %s", (answer, text, misconception) => {
    expect(checkAnswer(answer, text)).toMatchObject({ outcome: "WRONG", misconception_id: misconception });
  });

  it.each([
    [compare("0,50", "0,5"), "<"],
    [compare("0,7", "0,65"), "="],
  ])("%j with %j: wrong, but no bug rule applies", (answer, text) => {
    expect(checkAnswer(answer, text)).toMatchObject({ outcome: "WRONG", misconception_id: null });
  });

  it.each([["con nghĩ là"], ["<="], ["0,5 < 0,6"], ["0,25"]])("%j is unparseable", (text) => {
    expect(checkAnswer(gp01, text).outcome).toBe("UNPARSEABLE");
  });
});

describe("choice items", () => {
  it("reads 'Hoa ạ' as Hoa, not as option A", () => {
    expect(checkAnswer(answerOf("GP-08"), "Hoa ạ")).toMatchObject({ outcome: "CORRECT", normalized: "Hoa" });
  });

  it("maps a wrong option to its misconception with the option confidence", () => {
    expect(checkAnswer(answerOf("GP-08"), "Lan")).toMatchObject({
      outcome: "WRONG",
      misconception_id: "DEC-M01",
      confidence: 0.6,
    });
  });

  it("accepts aliases and option ids", () => {
    expect(checkAnswer(answerOf("GP-10"), "gói kẹo A").outcome).toBe("CORRECT");
    expect(checkAnswer(answerOf("CC-01"), "phần mười").outcome).toBe("CORRECT");
    expect(checkAnswer(answerOf("CC-01"), "B")).toMatchObject({
      outcome: "WRONG",
      misconception_id: "DEC-M03",
    });
  });

  it("does not guess between two options", () => {
    expect(checkAnswer(answerOf("CC-01"), "phần mười hay phần trăm").outcome).toBe("UNPARSEABLE");
  });
});

describe("boolean items", () => {
  const gp09 = answerOf("GP-09"); // An says 0,25 > 0,3: false

  it.each([["sai"], ["không đúng"], ["Bạn An nói sai vì 2 < 3"]])("%j is correct", (text) => {
    expect(checkAnswer(gp09, text).outcome).toBe("CORRECT");
  });

  it("'đúng' is DEC-M01", () => {
    expect(checkAnswer(gp09, "đúng")).toMatchObject({ outcome: "WRONG", misconception_id: "DEC-M01" });
  });
});

describe("numeric and order items", () => {
  it("numeric: GP-07", () => {
    expect(checkAnswer(answerOf("GP-07"), "6").outcome).toBe("CORRECT");
    expect(checkAnswer(answerOf("GP-07"), "x = 6").outcome).toBe("CORRECT");
    expect(checkAnswer(answerOf("GP-07"), "1")).toMatchObject({
      outcome: "WRONG",
      misconception_id: "DEC-M01",
    });
  });

  it("order: GP-06", () => {
    const gp06 = answerOf("GP-06");
    expect(checkAnswer(gp06, "0,2; 0,25; 0,3; 0,305")).toMatchObject({
      outcome: "CORRECT",
      normalized: "0,2; 0,25; 0,3; 0,305",
    });
    expect(checkAnswer(gp06, "0,305 > 0,3 > 0,25 > 0,2")).toMatchObject({
      outcome: "CORRECT",
      normalized: "0,2; 0,25; 0,3; 0,305",
    });
    expect(checkAnswer(gp06, "0,2; 0,3; 0,25; 0,305").outcome).toBe("WRONG");
    expect(checkAnswer(gp06, "0,2; 0,3").outcome).toBe("UNPARSEABLE");
  });
});

describe("intents", () => {
  const gp01 = answerOf("GP-01");
  it.each([
    ["", "NO_RESPONSE"],
    ["   ", "NO_RESPONSE"],
    ["con không biết", "HELP_REQUEST"],
    ["cô gợi ý cho con với", "HELP_REQUEST"],
    ["cho con đáp án đi", "ANSWER_DEMAND"],
  ])("%j → %s", (text, outcome) => {
    expect(checkAnswer(gp01, text).outcome).toBe(outcome);
  });

  it("open answers are left to the server (LLM + rubric)", () => {
    expect(checkAnswer(answerOf("CC-03"), "Vì hàng phần mười 7 > 6").outcome).toBe("NEEDS_LLM");
  });
});
