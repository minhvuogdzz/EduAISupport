import { describe, expect, it } from "vitest";

import { formatViDateTime, formatViDecimal, formatViTime, splitNumbers } from "./viNumber";

describe("formatViDecimal", () => {
  it.each([
    [0.25, "0,25"],
    [0.3, "0,3"],
    [0.1 + 0.2, "0,3"],
    [7, "7"],
    [1250.5, "1250,5"],
  ])("number %s → %s", (value, expected) => {
    expect(formatViDecimal(value)).toBe(expected);
  });

  it.each([
    ["0.25", "0,25"],
    ["0.50", "0,50"],
    ["0,5", "0,5"],
    ["12", "12"],
    [" 3.20 ", "3,20"],
  ])("string %j → %j (digit for digit)", (value, expected) => {
    expect(formatViDecimal(value)).toBe(expected);
  });

  it("leaves text that is not a single number untouched", () => {
    expect(formatViDecimal("0,25 < 0,3")).toBe("0,25 < 0,3");
    expect(formatViDecimal("Hoa")).toBe("Hoa");
  });
});

describe("dates are shown in Asia/Ho_Chi_Minh", () => {
  it("formats date and time", () => {
    expect(formatViDateTime("2026-09-30T01:15:02Z")).toBe("08:15 30/09/2026");
    expect(formatViTime("2026-09-30T01:15:02Z")).toBe("08:15:02");
  });
});

describe("splitNumbers", () => {
  it("keeps the decimal comma inside the number", () => {
    expect(splitNumbers("So sánh 0,25 … 0,3 nhé")).toEqual([
      { text: "So sánh ", isNumber: false },
      { text: "0,25", isNumber: true },
      { text: " … ", isNumber: false },
      { text: "0,3", isNumber: true },
      { text: " nhé", isNumber: false },
    ]);
  });

  it("treats a list separator as text", () => {
    expect(splitNumbers("0,3; 0,25").map((p) => p.text)).toEqual(["0,3", "; ", "0,25"]);
  });

  it("round-trips any text", () => {
    const text = "Lan chạy 60 m hết 9,8 giây; Hoa hết 9.75 giây.";
    expect(
      splitNumbers(text)
        .map((p) => p.text)
        .join(""),
    ).toBe(text);
  });
});
