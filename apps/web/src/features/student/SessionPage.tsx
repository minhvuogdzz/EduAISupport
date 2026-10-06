import type { ReactNode } from "react";
import { Link, useParams } from "react-router";

import type { SessionState } from "../../api/contract";
import { StarIcon } from "../../components/icons";
import { ACTIVITY_LABEL, capitalize } from "../../components/labels";
import { Mascot } from "../../components/Mascot";
import { MockBanner } from "../../components/MockBanner";
import { AnswerPanel } from "./AnswerPanel";
import { ChapterSession } from "./ChapterSession";
import { Conversation } from "./Conversation";
import { QuestionCard } from "./QuestionCard";
import { useStickToBottom } from "./useStickToBottom";
import { useTutorSession } from "./useTutorSession";

/** The student's tutor session: question, conversation, answer box, hint button (T09). */
export function SessionPage() {
  const { sessionId = "" } = useParams();
  const { view, busy, turns, submitAnswer, requestHint, choose, dismissNotice } = useTutorSession(sessionId);
  const scrollerRef = useStickToBottom(`${turns.length}:${view.typing?.text.length ?? 0}`);

  if (view.status === "loading") return <Message>Cô đang mở bài học…</Message>;
  if (view.status === "not_owner") {
    return (
      <Message link>
        Buổi học này của một bạn khác. Trên máy này, con hãy vào trang học sinh để học buổi của mình nhé.
      </Message>
    );
  }
  if (view.status === "not_found") {
    return <Message link>Không tìm thấy buổi học này. Con quay lại trang học sinh nhé.</Message>;
  }
  if (view.status === "error" || !view.state) {
    return <Message link>Chưa kết nối được. Con tải lại trang hoặc báo cô giáo nhé.</Message>;
  }

  const { state } = view;
  const tutorName = capitalize(state.persona.tutor_self);
  const notice = view.notice && (
    <p
      role="status"
      className="flex items-center justify-between gap-3 rounded-2xl bg-sky-100 px-4 py-3 text-lg text-sky-950"
    >
      {view.notice}
      <button type="button" onClick={dismissNotice} className="rounded-xl px-3 py-1 font-semibold underline">
        Đã hiểu
      </button>
    </p>
  );
  if (state.teaching) {
    return (
      <ChapterSession
        state={state}
        teaching={state.teaching}
        turns={turns}
        typing={view.typing}
        notice={notice}
        busy={busy}
        scrollerRef={scrollerRef}
        onSubmit={submitAnswer}
        onHint={() => void requestHint()}
        onChoose={(choice) => void choose(choice)}
      />
    );
  }
  return (
    // App-shell layout: only the middle scrolls, so the newest message is never hidden behind the
    // answer panel, and the question stays in view on tablets.
    <div className="flex h-dvh flex-col bg-amber-50">
      <title>{`${state.lesson.title} · CAVAT`}</title>
      <MockBanner />
      <SessionHeader state={state} />
      <div
        ref={scrollerRef}
        className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain [overflow-anchor:none]"
      >
        <main className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-4">
          {state.item && (
            <div className="md:sticky md:top-0 md:z-10 md:-mt-4 md:bg-amber-50 md:pt-4 md:pb-1">
              <QuestionCard item={state.item} total={state.progress.items_total} />
            </div>
          )}
          <Conversation
            turns={turns}
            typing={view.typing}
            tutorName={tutorName}
            studentName={state.student_display_name}
          />
          {notice}
        </main>
      </div>
      <footer className="shrink-0 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)]">
        {state.lifecycle_state === "COMPLETED" ? (
          <SessionComplete state={state} />
        ) : state.item ? (
          <AnswerPanel
            item={state.item}
            pendingChoice={state.pending_choice}
            allowed={state.allowed_commands}
            busy={busy}
            onSubmit={submitAnswer}
            onHint={() => void requestHint()}
            onChoose={(choice) => void choose(choice)}
          />
        ) : (
          <p className="px-4 py-5 text-center text-xl text-slate-700">Con chờ cô một chút nhé…</p>
        )}
      </footer>
    </div>
  );
}

function SessionHeader({ state }: { state: SessionState }) {
  const { items_done, items_total } = state.progress;
  const percent = items_total ? Math.round((items_done / items_total) * 100) : 0;
  return (
    <header className="border-b border-gold/25 bg-white">
      <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3">
        <Link to="/" aria-label="CAVAT, trang chủ" className="flex shrink-0 items-center gap-1.5 rounded-2xl">
          <Mascot size={40} />
          <span className="hidden text-lg font-extrabold text-brand-900 sm:inline">CAVAT</span>
        </Link>
        <div className="min-w-0 flex-1">
          {state.activity && (
            <p className="text-base font-medium text-brand-800">{ACTIVITY_LABEL[state.activity.type]}</p>
          )}
          <h1 className="truncate text-xl font-semibold">{state.lesson.title}</h1>
        </div>
        <p className="shrink-0 text-lg font-medium">
          <span className="sr-only">Học sinh: </span>
          {state.student_display_name}
        </p>
      </div>
      <div
        role="progressbar"
        aria-label="Tiến độ buổi học"
        aria-valuemin={0}
        aria-valuemax={items_total}
        aria-valuenow={items_done}
        aria-valuetext={`Đã xong ${items_done}/${items_total} câu`}
        className="h-2 bg-slate-100"
      >
        <div
          className="h-full bg-brand-500 transition-[width] duration-500"
          style={{ width: `${percent}%` }}
        />
      </div>
    </header>
  );
}

function SessionComplete({ state }: { state: SessionState }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center gap-2 px-4 py-5 text-center">
      <StarIcon className="size-12 text-amber-500" />
      <p className="text-2xl font-semibold">Con đã hoàn thành buổi học!</p>
      <p className="text-xl text-slate-700">
        Con đã làm {state.progress.items_done}/{state.progress.items_total} câu.
      </p>
      <Link
        to="/student"
        className="mt-2 rounded-2xl bg-brand-700 px-6 py-3 text-xl font-semibold text-white"
      >
        Về trang học sinh
      </Link>
    </div>
  );
}

function Message({ children, link = false }: { children: ReactNode; link?: boolean }) {
  return (
    <div className="min-h-dvh bg-amber-50">
      <MockBanner />
      <main className="mx-auto flex max-w-xl flex-col items-center gap-6 px-4 py-16 text-center">
        <p role="status" className="text-2xl">
          {children}
        </p>
        {link && (
          <Link to="/student" className="rounded-2xl bg-brand-700 px-6 py-3 text-xl font-semibold text-white">
            Trang học sinh
          </Link>
        )}
      </main>
    </div>
  );
}
