/**
 * MOCK ONLY: a small stand-in for the deterministic MathChecker of T01
 * (services/api/cavat/modules/assessment/math_checker.py), so the screens can run before the session
 * API exists. Real grading happens on the server; do not grow this into a second checker.
 */
import { formatViDecimal } from "../../lib/viNumber";
import type { Outcome } from "../contract";
import type {
  AnswerSpec,
  BooleanAnswer,
  ChoiceAnswer,
  CompareAnswer,
  NumericAnswer,
  OrderAnswer,
} from "./lessonTypes";

export interface MockCheck {
  outcome: Outcome;
  /** The checker's reading of the answer, vi-VN formatted (e.g. "0,25 > 0,3"); null if nothing was read. */
  normalized: string | null;
  misconception_id: string | null;
  confidence: number;
}

function check(
  outcome: Outcome,
  normalized: string | null = null,
  misconception_id: string | null = null,
  confidence = 0,
): MockCheck {
  return { outcome, normalized, misconception_id, confidence };
}

// Mock confidences. Only >= 0.7 counts as a clear misconception (T02 threshold).
const BUG_RULE_CONFIDENCE = 0.9;
const SPEC_WRONG_ANSWER_CONFIDENCE = 0.8;
const CHOICE_DEFAULT_CONFIDENCE = 0.6; // lesson_package.ChoiceOption.misconception_confidence default

/** Lower case, no diacritics, "đ" → "d", punctuation → space: "Hoa ạ." → "hoa a". */
export function normalizeVi(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[đĐ]/g, "d")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const ANSWER_DEMAND = /\b(cho|noi|dua|bao)\b.*\bdap an\b/;
const HELP_REQUEST = /\b(khong biet|chua biet|khong hieu|chua hieu|goi y|giup (con|em|minh|to|toi))\b/;

// ---------------------------------------------------------------- decimals

export interface Decimal {
  integer: bigint;
  fraction: string;
}

interface NumberToken {
  token: string;
  value: Decimal;
}

/** "0,25" or "0.25" → exact decimal (no floating point). */
export function parseDecimal(token: string): Decimal | null {
  const match = /^(\d+)(?:[.,](\d+))?$/.exec(token.trim());
  return match ? { integer: BigInt(match[1]), fraction: match[2] ?? "" } : null;
}

export function compareDecimals(a: Decimal, b: Decimal): -1 | 0 | 1 {
  if (a.integer !== b.integer) return a.integer < b.integer ? -1 : 1;
  const width = Math.max(a.fraction.length, b.fraction.length);
  const fa = a.fraction.padEnd(width, "0");
  const fb = b.fraction.padEnd(width, "0");
  return fa === fb ? 0 : fa < fb ? -1 : 1; // equal-length digit strings order like numbers
}

function numbersIn(text: string): NumberToken[] {
  return [...text.matchAll(/\d+(?:[.,]\d+)?/g)].map((m) => ({ token: m[0], value: parseDecimal(m[0])! }));
}

function decimalOf(token: string): Decimal {
  const value = parseDecimal(token);
  if (!value) throw new Error(`lesson number ${token} is not a decimal`);
  return value;
}

// ---------------------------------------------------------------- compare

type Relation = "<" | "=" | ">";
const RELATION_OF: Record<-1 | 0 | 1, Relation> = { [-1]: "<", 0: "=", 1: ">" };
const FLIPPED: Record<Relation, Relation> = { "<": ">", "=": "=", ">": "<" };

function relationIn(raw: string, norm: string): Relation | null {
  const symbols = new Set(raw.match(/[<>=]/g) ?? []);
  if (symbols.size > 0) return symbols.size === 1 ? ([...symbols][0] as Relation) : null;
  const words = new Set<Relation>();
  if (/\b(be|nho) hon\b/.test(norm)) words.add("<");
  if (/\blon hon\b/.test(norm)) words.add(">");
  if (/\bbang( nhau)?\b/.test(norm)) words.add("=");
  return words.size === 1 ? [...words][0] : null;
}

const stripLeadingZeros = (digits: string) => digits.replace(/^0+/, "");

/** Mock bug rules DEC-M01…M05 for a wrong relation between left and right. */
function compareBugRule(left: Decimal, right: Decimal, correct: Relation, said: Relation): string | null {
  if (said === correct) return null;
  if (left.integer !== right.integer) return "DEC-M04"; // 2,1 < 1,99: integer part ignored
  if (said === "=") {
    return stripLeadingZeros(left.fraction) === stripLeadingZeros(right.fraction) ? "DEC-M03" : null; // 0,05 = 0,5
  }
  if (left.fraction.length === right.fraction.length) return null;
  const longerIsLeft = left.fraction.length > right.fraction.length;
  const saysLongerIsLarger = longerIsLeft === (said === ">");
  if (correct === "=") return saysLongerIsLarger ? "DEC-M05" : null; // 0,50 > 0,5
  return saysLongerIsLarger ? "DEC-M01" : "DEC-M02"; // 0,25 > 0,3 | 0,4 > 0,45
}

function checkCompare(answer: CompareAnswer, raw: string, norm: string): MockCheck {
  let said = relationIn(raw, norm);
  if (!said) return check("UNPARSEABLE");
  const left = decimalOf(answer.left);
  const right = decimalOf(answer.right);
  const numbers = numbersIn(raw);
  if (numbers.length > 0) {
    // "0,3 > 0,25" answers "0,25 … 0,3" too: read the relation in the item's order.
    if (numbers.length !== 2) return check("UNPARSEABLE");
    const [first, second] = numbers.map((n) => n.value);
    const sameOrder = compareDecimals(first, left) === 0 && compareDecimals(second, right) === 0;
    const reversed = compareDecimals(first, right) === 0 && compareDecimals(second, left) === 0;
    if (!sameOrder && !reversed) return check("UNPARSEABLE");
    if (!sameOrder) said = FLIPPED[said];
  }
  const correct = RELATION_OF[compareDecimals(left, right)];
  const normalized = `${formatViDecimal(answer.left)} ${said} ${formatViDecimal(answer.right)}`;
  if (said === correct) return check("CORRECT", normalized);
  const misconception = compareBugRule(left, right, correct, said);
  return check("WRONG", normalized, misconception, misconception ? BUG_RULE_CONFIDENCE : 0);
}

// ---------------------------------------------------------------- choice, boolean, numeric, order

function checkChoice(answer: ChoiceAnswer, norm: string): MockCheck {
  const padded = ` ${norm} `;
  const matches = answer.options.filter(
    (option) =>
      norm === normalizeVi(option.id) ||
      [option.text, ...(option.aliases ?? [])].some((label) => padded.includes(` ${normalizeVi(label)} `)),
  );
  if (matches.length !== 1) return check("UNPARSEABLE");
  const [option] = matches;
  if (option.correct) return check("CORRECT", option.text);
  const misconception = option.misconceptions?.[0] ?? null;
  const confidence = misconception ? (option.misconception_confidence ?? CHOICE_DEFAULT_CONFIDENCE) : 0;
  return check("WRONG", option.text, misconception, confidence);
}

const SAYS_FALSE = /\b(sai|khong dung|chua dung|khong phai|chua phai)\b/;
const SAYS_TRUE = /\b(dung|phai)\b/;

function checkBoolean(answer: BooleanAnswer, norm: string): MockCheck {
  const verdict = SAYS_FALSE.test(norm) ? false : SAYS_TRUE.test(norm) ? true : null;
  if (verdict === null) return check("UNPARSEABLE");
  const normalized = verdict ? "Đúng" : "Sai";
  if (verdict === answer.value) return check("CORRECT", normalized);
  const misconception = answer.wrong_answers?.[String(verdict)] ?? null;
  return check("WRONG", normalized, misconception, misconception ? SPEC_WRONG_ANSWER_CONFIDENCE : 0);
}

function checkNumeric(answer: NumericAnswer, raw: string): MockCheck {
  const [first] = numbersIn(raw);
  if (!first) return check("UNPARSEABLE");
  const normalized = formatViDecimal(first.token);
  if (compareDecimals(first.value, decimalOf(answer.value)) === 0) return check("CORRECT", normalized);
  const key = Object.keys(answer.wrong_answers ?? {}).find((wrong) => {
    const value = parseDecimal(wrong);
    return value !== null && compareDecimals(value, first.value) === 0;
  });
  const misconception = key ? (answer.wrong_answers?.[key] ?? null) : null;
  return check("WRONG", normalized, misconception, misconception ? SPEC_WRONG_ANSWER_CONFIDENCE : 0);
}

function isSorted(values: Decimal[], direction: "asc" | "desc"): boolean {
  const step = direction === "asc" ? -1 : 1;
  return values.every((value, i) => i === 0 || compareDecimals(values[i - 1], value) === step);
}

function checkOrder(answer: OrderAnswer, raw: string): MockCheck {
  const tokens = numbersIn(raw);
  const expected = answer.numbers.map(decimalOf).sort(compareDecimals);
  const given = tokens.map((t) => t.value);
  const sameNumbers =
    given.length === expected.length &&
    [...given].sort(compareDecimals).every((value, i) => compareDecimals(value, expected[i]) === 0);
  if (!sameNumbers) return check("UNPARSEABLE");
  const direction = answer.direction ?? "asc";
  const listed = tokens.map((t) => formatViDecimal(t.token));
  if (isSorted(given, direction)) return check("CORRECT", listed.join("; "));
  // "0,305 > 0,3 > 0,25 > 0,2" states the ascending order, read from right to left.
  const chain = direction === "asc" ? ">" : "<";
  const reverse = direction === "asc" ? "desc" : "asc";
  if (raw.includes(chain) && !raw.includes(FLIPPED[chain]) && isSorted(given, reverse)) {
    return check("CORRECT", listed.reverse().join("; "));
  }
  return check("WRONG", listed.join("; "));
}

/** Reads one student message against an item answer (MOCK ONLY, see the file header). */
export function checkAnswer(answer: AnswerSpec, text: string): MockCheck {
  if (!text.trim()) return check("NO_RESPONSE");
  const norm = normalizeVi(text); // empty for a bare "<": symbols are read from the raw text
  if (ANSWER_DEMAND.test(norm)) return check("ANSWER_DEMAND");
  if (HELP_REQUEST.test(norm)) return check("HELP_REQUEST");
  switch (answer.type) {
    case "compare":
      return checkCompare(answer, text, norm);
    case "choice":
      return checkChoice(answer, norm);
    case "boolean":
      return checkBoolean(answer, norm);
    case "numeric":
      return checkNumeric(answer, text);
    case "order":
      return checkOrder(answer, text);
    case "open":
      return check("NEEDS_LLM");
  }
}
