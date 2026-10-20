import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import type { AnswerFormat, CommandType, CurrentItem, MicroChoice } from "../../api/contract";
import { LightbulbIcon, SendIcon } from "../../components/icons";

interface AnswerPanelProps {
  item: CurrentItem;
  pendingChoice: MicroChoice[] | null;
  allowed: CommandType[];
  busy: boolean;
  onSubmit: (text: string) => Promise<boolean>;
  onHint: () => void;
  onChoose: (choice: MicroChoice) => void;
  /** Replies in words to the teaching loop (theory question, retell) have no hint to ask for. */
  showHint?: boolean;
  placeholder?: string;
  /** UI-1: what starts the answer row (the voice switch), so the footer is one row. */
  leading?: ReactNode;
}

/** Signs a 10-year-old cannot easily type on a tablet keyboard. */
const SYMBOLS: Partial<Record<AnswerFormat, string[]>> = {
  compare: ["<", ">", "=", ","],
  numeric: [","],
  order: [",", ";"],
};

const SYMBOL_NAME: Record<string, string> = {
  "<": "dấu bé hơn",
  ">": "dấu lớn hơn",
  "=": "dấu bằng",
  ",": "dấu phẩy",
  ";": "dấu chấm phẩy",
};

function quickAnswers(item: CurrentItem): string[] {
  if (item.answer_format === "boolean") return ["Đúng", "Sai"];
  if (item.answer_format === "choice") return item.options.map((option) => option.text);
  return [];
}

function prefersKeyboard(): boolean {
  return window.matchMedia?.("(pointer: fine)").matches ?? false;
}

export function AnswerPanel({
  item,
  pendingChoice,
  allowed,
  busy,
  onSubmit,
  onHint,
  onChoose,
  showHint = true,
  placeholder,
  leading,
}: AnswerPanelProps) {
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const explaining = item.expecting === "EXPLANATION";
  const canAnswer = allowed.includes("ANSWER");
  const answers = explaining ? [] : quickAnswers(item);
  const symbols = SYMBOLS[item.answer_format] ?? [];

  // On a laptop, put the cursor back in the box when it is the student's turn again.
  // On a tablet, do not: focusing would pop up the on-screen keyboard over the conversation.
  useEffect(() => {
    if (!busy && prefersKeyboard()) inputRef.current?.focus();
  }, [busy, item.item_attempt_id]);

  /** Inserts a sign at the cursor. The buttons do not take focus, so the cursor stays put. */
  function insert(symbol: string) {
    const input = inputRef.current;
    const start = input?.selectionStart ?? draft.length;
    const end = input?.selectionEnd ?? draft.length;
    setDraft(draft.slice(0, start) + symbol + draft.slice(end));
    requestAnimationFrame(() => {
      if (input && document.activeElement === input) input.setSelectionRange(start + 1, start + 1);
    });
  }

  async function submit() {
    const text = draft.trim();
    if (!text || busy || !canAnswer) return;
    setDraft("");
    if (!(await onSubmit(text))) setDraft((current) => current || text); // not sent: give it back
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter is a new line. Not while an IME (Telex, VNI…) is composing a letter.
    const composing = event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229;
    if (event.key === "Enter" && !event.shiftKey && !composing) {
      event.preventDefault();
      void submit();
    }
  }

  const bigButton =
    "min-h-11 rounded-xl px-3.5 text-[15px] font-semibold disabled:cursor-not-allowed disabled:opacity-50";
  const decimals = symbols.includes(",") && !explaining;
  const hint =
    placeholder ??
    (explaining
      ? "Con giải thích ở đây…"
      : decimals
        ? "Con trả lời ở đây (số thập phân viết dấu phẩy: 0,25)"
        : "Con trả lời ở đây…");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-1.5 px-3 py-2 sm:px-4">
      {pendingChoice && (
        <div role="group" aria-label="Con chọn một cách" className="flex flex-wrap gap-2">
          {pendingChoice.map((choice) => (
            <button
              key={choice.choice_id}
              type="button"
              disabled={busy || !allowed.includes("CHOICE")}
              onClick={() => onChoose(choice)}
              className={`${bigButton} bg-amber-300 text-amber-950 hover:bg-amber-400`}
            >
              {choice.label}
            </button>
          ))}
        </div>
      )}

      {(answers.length > 0 || symbols.length > 0) && (
        <div className="flex flex-wrap gap-1.5" aria-label="Chọn nhanh">
          {answers.map((answer) => (
            <button
              key={answer}
              type="button"
              disabled={!canAnswer}
              onClick={() => setDraft(answer)}
              className={`${bigButton} bg-white font-medium text-slate-900 ring-1 ring-slate-200 hover:ring-brand-500`}
            >
              {answer}
            </button>
          ))}
          {symbols.map((symbol) => (
            <button
              key={symbol}
              type="button"
              aria-label={SYMBOL_NAME[symbol]}
              disabled={!canAnswer}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => insert(symbol)}
              className="size-11 rounded-xl bg-white text-xl font-bold text-slate-900 ring-1 ring-slate-200 hover:ring-brand-500 disabled:opacity-50"
            >
              {symbol}
            </button>
          ))}
        </div>
      )}

      <form
        className="flex items-end gap-1.5 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-sm focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-100"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        {leading}
        <label htmlFor="answer" className="sr-only">
          {explaining ? "Lời giải thích của con" : "Câu trả lời của con"}
        </label>
        <textarea
          id="answer"
          ref={inputRef}
          rows={explaining ? 2 : 1}
          value={draft}
          maxLength={500}
          disabled={!canAnswer}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={hint}
          lang="vi"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          className="min-h-11 min-w-0 flex-1 resize-none bg-transparent px-2 py-2.5 text-base leading-6 placeholder:text-slate-400 focus-visible:outline-none disabled:opacity-60"
        />
        {showHint && (
          <button
            type="button"
            onClick={onHint}
            disabled={busy || !allowed.includes("HINT_REQUEST")}
            aria-label="Xin gợi ý"
            title="Xin gợi ý"
            className={`${bigButton} inline-flex shrink-0 items-center gap-1.5 bg-amber-50 text-amber-900 ring-1 ring-amber-200 hover:bg-amber-100`}
          >
            <LightbulbIcon className="size-5" />
            <span className="hidden sm:inline">Gợi ý</span>
          </button>
        )}
        <button
          type="submit"
          disabled={busy || !canAnswer || !draft.trim()}
          aria-label="Gửi"
          className={`${bigButton} inline-flex shrink-0 items-center gap-1.5 bg-brand-700 text-white hover:bg-brand-800`}
        >
          <span className="hidden sm:inline">Gửi</span>
          <SendIcon className="size-5" />
        </button>
      </form>
      {busy && (
        <p className="px-1 text-xs text-slate-500" aria-live="polite">
          Cô đang trả lời…
        </p>
      )}
    </div>
  );
}
