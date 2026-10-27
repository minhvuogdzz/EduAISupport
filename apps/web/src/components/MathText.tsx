import { splitNumbers } from "../lib/viNumber";
import { FigureImage, pullFigures, useFigures } from "./Figures";

// "0,25 … 0,3": the blank means nothing without both numbers, so the three stay on one line.
const FILL_IN = /(\d+(?:[.,]\d+)?\s*…\s*\d+(?:[.,]\d+)?)/;

/**
 * Text with its numbers styled as one unit ("0,25" never breaks at the comma, digits line up).
 * The text itself is never changed. With `blanks`, the "…" of a fill-in stem becomes a visible box.
 */
export function MathText({ text, blanks = false }: { text: string; blanks?: boolean }) {
  const figures = useFigures();
  const { text: words, found } = pullFigures(text, figures);
  if (found.length === 0) return <Words text={text} blanks={blanks} />;
  // FIG-1: the picture of a "[Hình: …]" goes above the words; the description stays its alternative text.
  return (
    <>
      {found.map((figure) => (
        <FigureImage key={figure.figure_id} figure={figure} />
      ))}
      <Words text={words} blanks={blanks} />
    </>
  );
}

function Words({ text, blanks }: { text: string; blanks: boolean }) {
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
            <span className="mx-1 inline-block min-w-[2.5em] rounded-lg border-2 border-dashed border-brand-600 bg-brand-50 px-2 text-center text-brand-700">
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
