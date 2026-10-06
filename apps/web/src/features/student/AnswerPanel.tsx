import { useEffect, useRef, useState, type KeyboardEvent } from "react";

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
    "min-h-14 rounded-2xl px-5 text-xl font-semibold disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3 px-4 py-3">
      {pendingChoice && (
        <div role="group" aria-label="Con chọn một cách" className="flex flex-wrap gap-3">
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
        <div className="flex flex-wrap gap-2" aria-label="Chọn nhanh">
          {answers.map((answer) => (
            <button
              key={answer}
              type="button"
              disabled={!canAnswer}
              onClick={() => setDraft(answer)}
              className={`${bigButton} bg-white text-slate-900 ring-2 ring-slate-300 hover:ring-teal-600`}
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
              className="size-14 rounded-2xl bg-white text-3xl font-bold text-slate-900 ring-2 ring-slate-300 hover:ring-teal-600 disabled:opacity-50"
            >
              {symbol}
            </button>
          ))}
        </div>
      )}

      <form
        className="flex items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label htmlFor="answer" className="sr-only">
          {explaining ? "Lời giải thích của con" : "Câu trả lời của con"}
        </label>
        <textarea
          id="answer"
          ref={inputRef}
          rows={2}
          value={draft}
          maxLength={500}
          disabled={!canAnswer}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder ?? (explaining ? "Con giải thích ở đây…" : "Con viết câu trả lời ở đây…")}
          lang="vi"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          className="min-h-16 flex-1 resize-none rounded-2xl border-2 border-slate-300 bg-white px-4 py-3 text-2xl focus:border-teal-600 disabled:bg-slate-100"
        />
        <button
          type="submit"
          disabled={busy || !canAnswer || !draft.trim()}
          className={`${bigButton} inline-flex items-center gap-2 bg-teal-700 text-white hover:bg-teal-800`}
        >
          Gửi
          <SendIcon className="size-5" />
        </button>
      </form>

      <div className="flex flex-wrap items-center justify-between gap-3">
        {showHint && (
          <button
            type="button"
            onClick={onHint}
            disabled={busy || !allowed.includes("HINT_REQUEST")}
            className={`${bigButton} inline-flex items-center gap-2 bg-amber-100 text-amber-950 ring-2 ring-amber-300 hover:bg-amber-200`}
          >
            <LightbulbIcon className="size-6" />
            Xin gợi ý
          </button>
        )}
        <p className="text-base text-slate-600" aria-live="polite">
          {busy
            ? "Cô đang trả lời…"
            : symbols.includes(",") && !explaining
              ? "Viết số thập phân bằng dấu phẩy, ví dụ 0,25."
              : ""}
        </p>
      </div>
    </div>
  );
}
