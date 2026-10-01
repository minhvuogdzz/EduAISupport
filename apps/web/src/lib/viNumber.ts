/**
 * Vietnamese display of numbers and times (blueprint 01, R7): decimal comma ("0,25"), times in
 * Asia/Ho_Chi_Minh (PART 28.1).
 *
 * The UI never rewrites what a student typed; these helpers are for values the UI formats itself
 * (checker output, scores, timestamps).
 */

// No thousands grouping: in vi-VN "1.250" means 1250, which a grade-5 student can misread as 1,25.
const VI_DECIMAL = new Intl.NumberFormat("vi-VN", { useGrouping: false, maximumFractionDigits: 10 });

const VI_DATETIME = new Intl.DateTimeFormat("vi-VN", {
  timeZone: "Asia/Ho_Chi_Minh",
  hour: "2-digit",
  minute: "2-digit",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const VI_TIME = new Intl.DateTimeFormat("vi-VN", {
  timeZone: "Asia/Ho_Chi_Minh",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

/**
 * 0.25 → "0,25". Strings are machine format (dot = decimal point) or already vi-VN, and are converted
 * digit for digit so trailing zeros survive: "0.50" → "0,50" (DEC-M05 items depend on that zero).
 */
export function formatViDecimal(value: number | string): string {
  if (typeof value === "number") return Number.isFinite(value) ? VI_DECIMAL.format(value) : String(value);
  const match = /^(-?\d+)(?:[.,](\d+))?$/.exec(value.trim());
  if (!match) return value;
  const [, integer, fraction] = match;
  return fraction === undefined ? integer : `${integer},${fraction}`;
}

/** "2026-09-30T01:15:02Z" → "08:15 30/09/2026". */
export function formatViDateTime(iso: string): string {
  return VI_DATETIME.format(new Date(iso));
}

/** "2026-09-30T01:15:02Z" → "08:15:02". */
export function formatViTime(iso: string): string {
  return VI_TIME.format(new Date(iso));
}

export interface TextPart {
  text: string;
  isNumber: boolean;
}

const NUMBER_TOKEN = /\d+(?:[.,]\d+)?/g;

/** Splits text into plain and number parts, so numbers can be styled as a unit. Never changes text. */
export function splitNumbers(text: string): TextPart[] {
  const parts: TextPart[] = [];
  let last = 0;
  for (const match of text.matchAll(NUMBER_TOKEN)) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index), isNumber: false });
    parts.push({ text: match[0], isNumber: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), isNumber: false });
  return parts;
}
