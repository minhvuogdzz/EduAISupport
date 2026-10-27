import type { ReactNode, Ref } from "react";
import { Link } from "react-router";

import type { CurrentItem, MicroChoice, Modality, SessionState, TeachingView } from "../../api/contract";
import { FiguresProvider } from "../../components/Figures";
import { StarIcon } from "../../components/icons";
import { capitalize, TEACHING_STEPS } from "../../components/labels";
import { MathText } from "../../components/MathText";
import { Mascot } from "../../components/Mascot";
import { MockBanner } from "../../components/MockBanner";
import { KnowledgeMap } from "../teaching/KnowledgeMap";
import { StepBar } from "../teaching/StepBar";
import { AnswerPanel } from "./AnswerPanel";
import { Conversation } from "./Conversation";
import { QuestionCard } from "./QuestionCard";
import type { DisplayTurn, TutorView } from "./tutorSession";
import { useVoiceLive } from "./voice/useVoiceLive";
import { VoiceStatus, VoiceToggle } from "./voice/VoiceBar";

interface ChapterSessionProps {
  state: SessionState;
  teaching: TeachingView;
  turns: DisplayTurn[];
  typing: TutorView["typing"];
  notice: ReactNode;
  busy: boolean;
  scrollerRef: Ref<HTMLDivElement>;
  onSubmit: (text: string, modality?: Modality) => Promise<boolean>;
  onHint: () => void;
  onChoose: (choice: MicroChoice) => void;
}

/** What the card above an item says in a chapter session: the step of the cycle it belongs to. */
const ITEM_STEP_LABEL: Record<number, string> = {
  1: "Ôn bài nền",
  3: "Kiểm tra hiểu",
  4: "Cô làm cùng con",
  5: "Luyện tập",
  6: "Vận dụng",
  7: "Ôn bài cũ",
};

/**
 * A chapter session (M1-7): the teaching loop of plan v1 on the knowledge graph. The node map shows
 * where the student is in the chapter; the step bar shows where the student is in the teaching cycle of
 * the current node. The tutor's theory and worked examples are cards in the conversation.
 */
export function ChapterSession({
  state,
  teaching,
  turns,
  typing,
  notice,
  busy,
  scrollerRef,
  onSubmit,
  onHint,
  onChoose,
}: ChapterSessionProps) {
  const tutorName = capitalize(state.persona.tutor_self);
  const voice = useVoiceLive({
    turns,
    canSpeak:
      state.lifecycle_state === "ACTIVE" &&
      !busy &&
      !state.pending_choice &&
      (Boolean(state.item) || teaching.awaiting === "THEORY_REPLY" || teaching.awaiting === "RETELL"),
    submit: onSubmit,
  });
  const current = teaching.nodes.find((node) => node.node_id === teaching.current_node_id) ?? null;
  const active = state.lifecycle_state === "ACTIVE";
  const map = (
    <KnowledgeMap
      nodes={teaching.nodes}
      relations={teaching.relations}
      title={`Bản đồ bài học chương ${teaching.chapter.title}`}
    />
  );
  // Desktop: in the side column, always in view. Tablet and phone: at the top of the conversation.
  const steps = active && current ? <StepBar step={teaching.step} nodeName={current.name} /> : null;
  const replying = active && (teaching.awaiting === "THEORY_REPLY" || teaching.awaiting === "RETELL");
  const reply: CurrentItem | null =
    replying && teaching.input_id
      ? {
          item_attempt_id: teaching.input_id,
          item_id: "",
          stem: teaching.prompt ?? "",
          answer_format: "open",
          options: [],
          expecting: teaching.awaiting === "RETELL" ? "EXPLANATION" : "ANSWER",
          position: 0,
        }
      : null;
  // UI-1: while the tutor's last words are the question itself, a pinned card would say it a second time;
  // it comes back (pinned) once the tutor says something else, a hint for instance.
  const lastTutor = [...turns].reverse().find((turn) => turn.actor === "tutor")?.text ?? "";
  const promptShown = Boolean(teaching.prompt) && !lastTutor.includes(teaching.prompt ?? "");
  const itemShown = Boolean(state.item) && !lastTutor.includes(state.item?.stem ?? "");

  return (
    <FiguresProvider chapterId={teaching.chapter.chapter_id} who="student">
      <div className="flex h-dvh flex-col bg-paper">
        <title>{`${teaching.chapter.title} · CAVAT`}</title>
        <MockBanner />
        <ChapterHeader state={state} teaching={teaching} nodeName={current?.name ?? null} />
        <div className="flex min-h-0 flex-1">
          <div
            ref={scrollerRef}
            className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain [overflow-anchor:none]"
          >
            <main className="mx-auto flex w-full max-w-3xl flex-col gap-3 px-3 py-3 sm:px-4">
              <div className="flex flex-col gap-2 lg:hidden">
                {steps && <div className="rounded-2xl bg-white px-4 py-3 ring-1 ring-slate-200">{steps}</div>}
                <details className="rounded-2xl bg-white px-4 py-2.5 ring-1 ring-slate-200">
                  <summary className="cursor-pointer text-sm font-semibold">
                    Bản đồ bài học · {teaching.passed}/{teaching.total} bài đã qua
                  </summary>
                  <div className="mt-3">{map}</div>
                </details>
              </div>
              {state.item
                ? itemShown && (
                    <div className="md:sticky md:top-0 md:z-10 md:-mt-3 md:bg-paper md:pt-3 md:pb-1">
                      <QuestionCard
                        item={state.item}
                        total={0}
                        label={ITEM_STEP_LABEL[teaching.step ?? 0] ?? "Câu hỏi"}
                      />
                    </div>
                  )
                : reply &&
                  teaching.prompt &&
                  promptShown && (
                    <div className="md:sticky md:top-0 md:z-10 md:-mt-3 md:bg-paper md:pt-3 md:pb-1">
                      <PromptCard prompt={teaching.prompt} retell={teaching.awaiting === "RETELL"} />
                    </div>
                  )}
              <Conversation
                turns={turns}
                typing={typing}
                tutorName={tutorName}
                studentName={state.student_display_name}
              />
              {notice}
            </main>
          </div>
          <aside
            aria-label="Bản đồ bài học"
            className="hidden w-[22rem] shrink-0 overflow-y-auto border-l border-slate-200 bg-white px-4 py-3 lg:block"
          >
            {steps && <div className="mb-4 rounded-2xl bg-brand-50/70 px-3 py-3">{steps}</div>}
            <h2 className="text-sm font-semibold">Bản đồ bài học</h2>
            <p className="mb-2 text-xs text-slate-500">
              {teaching.passed}/{teaching.total} bài đã qua
            </p>
            {map}
          </aside>
        </div>
        <footer className="shrink-0 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)]">
          {state.lifecycle_state !== "COMPLETED" && <VoiceStatus voice={voice} />}
          {state.lifecycle_state === "COMPLETED" ? (
            <ChapterComplete teaching={teaching} />
          ) : state.item ? (
            <AnswerPanel
              item={state.item}
              pendingChoice={state.pending_choice}
              allowed={state.allowed_commands}
              busy={busy}
              onSubmit={onSubmit}
              onHint={onHint}
              onChoose={onChoose}
              leading={<VoiceToggle voice={voice} />}
            />
          ) : reply ? (
            <AnswerPanel
              item={reply}
              pendingChoice={null}
              allowed={state.allowed_commands}
              busy={busy}
              onSubmit={onSubmit}
              onHint={onHint}
              onChoose={onChoose}
              showHint={false}
              leading={<VoiceToggle voice={voice} />}
              placeholder={
                teaching.awaiting === "RETELL" ? "Con nói lại bằng lời của con…" : "Con trả lời cô ở đây…"
              }
            />
          ) : (
            <p className="px-4 py-3 text-center text-sm text-slate-600">Con chờ cô một chút nhé…</p>
          )}
        </footer>
      </div>
    </FiguresProvider>
  );
}

function ChapterHeader({
  state,
  teaching,
  nodeName,
}: {
  state: SessionState;
  teaching: TeachingView;
  nodeName: string | null;
}) {
  const percent = teaching.total ? Math.round((teaching.passed / teaching.total) * 100) : 0;
  const step = teaching.step ? TEACHING_STEPS[teaching.step - 1] : null;
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex items-center gap-3 px-4 py-2 lg:max-w-none">
        <Link to="/" aria-label="CAVAT, trang chủ" className="flex shrink-0 items-center gap-1.5 rounded-2xl">
          <Mascot size={32} />
          <span className="hidden font-extrabold text-brand-900 sm:inline">CAVAT</span>
        </Link>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium text-brand-700">
            {state.lifecycle_state === "COMPLETED"
              ? "Tổng kết"
              : [nodeName, step].filter(Boolean).join(" · ")}
          </p>
          <h1 className="truncate text-base font-semibold">{teaching.chapter.title}</h1>
        </div>
        <p className="shrink-0 text-sm font-medium text-slate-700">
          <span className="sr-only">Học sinh: </span>
          {state.student_display_name}
        </p>
      </div>
      <div
        role="progressbar"
        aria-label="Tiến độ chương"
        aria-valuemin={0}
        aria-valuemax={teaching.total}
        aria-valuenow={teaching.passed}
        aria-valuetext={`Đã qua ${teaching.passed}/${teaching.total} bài`}
        className="h-1 bg-slate-100"
      >
        <div
          className="h-full bg-brand-500 transition-[width] duration-500"
          style={{ width: `${percent}%` }}
        />
      </div>
    </header>
  );
}

/** The question the student answers in words: the end of a theory explanation, or the retell. */
function PromptCard({ prompt, retell }: { prompt: string; retell: boolean }) {
  return (
    <section
      aria-labelledby="prompt-title"
      className="rounded-2xl bg-white px-4 py-3 shadow-sm ring-1 ring-sky-200"
    >
      <h2 id="prompt-title" className="text-xs font-semibold tracking-wide text-sky-800 uppercase">
        {retell ? "Con nói lại giúp cô" : "Cô hỏi con"}
      </h2>
      <p className="mt-1 text-[17px] leading-snug font-medium text-pretty md:text-lg">
        <MathText text={prompt} />
      </p>
    </section>
  );
}

function ChapterComplete({ teaching }: { teaching: TeachingView }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center gap-2 px-4 py-5 text-center">
      <StarIcon className="size-10 text-amber-500" />
      <p className="text-xl font-semibold">Con đã hoàn thành buổi học!</p>
      <p className="text-base text-slate-700">
        Con đã qua {teaching.passed}/{teaching.total} bài của chương {teaching.chapter.title}.
      </p>
      <Link
        to="/student"
        className="mt-2 rounded-xl bg-brand-700 px-5 py-2.5 text-base font-semibold text-white"
      >
        Về trang học sinh
      </Link>
    </div>
  );
}
