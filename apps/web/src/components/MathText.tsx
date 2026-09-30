import { splitNumbers } from "../lib/viNumber";

// "0,25 … 0,3": the blank means nothing without both numbers, so the three stay on one line.
const FILL_IN = /(\d+(?:[.,]\d+)?\s*…\s*\d+(?:[.,]\d+)?)/;

/**
 * Text with its numbers styled as one unit ("0,25" never breaks at the comma, digits line up).
 * The text itself is never changed. With `blanks`, the "…" of a fill-in stem becomes a visible box.
 */
export function MathText({ text, blanks = false }: { text: string; blanks?: boolean }) {
  if (!blanks) return <Numbers text={text} />;
  return (
    <>
      {text.split(FILL_IN).map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} className="whitespace-nowrap">
            <Numbers text={part} blanks />
          </span>
        ) : (
          <Numbers key={i} text={part} blanks />
        ),
      )}
    </>
  );
}

function Numbers({ text, blanks = false }: { text: string; blanks?: boolean }) {
  return (
    <>
      {splitNumbers(text).map((part, i) =>
        part.isNumber ? (
          <span key={i} className="font-semibold whitespace-nowrap tabular-nums">
            {part.text}
          </span>
        ) : blanks ? (
          <WithBlanks key={i} text={part.text} />
        ) : (
          part.text
        ),
      )}
    </>
  );
}

function WithBlanks({ text }: { text: string }) {
  return (
    <>
      {text.split("…").map((piece, i) => (
        <span key={i}>
          {i > 0 && (
            <span className="mx-1 inline-block min-w-[2.5em] rounded-lg border-2 border-dashed border-teal-600 bg-teal-50 px-2 text-center text-teal-700">
              <span aria-hidden="true">…</span>
              <span className="sr-only">chỗ trống</span>
            </span>
          )}
          {piece}
        </span>
      ))}
    </>
  );
}
