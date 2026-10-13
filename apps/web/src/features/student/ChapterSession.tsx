import type { ReactNode, Ref } from "react";
import { Link } from "react-router";

import type { CurrentItem, MicroChoice, Modality, SessionState, TeachingView } from "../../api/contract";
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
import { VoiceBar } from "./voice/VoiceBar";

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

  return (
    <div className="flex h-dvh flex-col bg-amber-50">
      <title>{`${teaching.chapter.title} · CAVAT`}</title>
      <MockBanner />
      <ChapterHeader state={state} teaching={teaching} nodeName={current?.name ?? null} />
      <div className="flex min-h-0 flex-1">
        <div
          ref={scrollerRef}
          className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain [overflow-anchor:none]"
        >
          <main className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-4">
            <div className="flex flex-col gap-4 lg:hidden">
              {steps && <div className="rounded-3xl bg-white p-4 ring-1 ring-slate-200">{steps}</div>}
              <details className="rounded-3xl bg-white p-4 ring-1 ring-slate-200">
                <summary className="cursor-pointer font-semibold">
                  Bản đồ bài học · {teaching.passed}/{teaching.total} bài đã qua
                </summary>
                <div className="mt-3">{map}</div>
              </details>
            </div>
            {state.item ? (
              <div className="md:sticky md:top-0 md:z-10 md:-mt-4 md:bg-amber-50 md:pt-4 md:pb-1">
                <QuestionCard
                  item={state.item}
                  total={0}
                  label={ITEM_STEP_LABEL[teaching.step ?? 0] ?? "Câu hỏi"}
                />
              </div>
            ) : (
              reply &&
              teaching.prompt && (
                <div className="md:sticky md:top-0 md:z-10 md:-mt-4 md:bg-amber-50 md:pt-4 md:pb-1">
                  <PromptCard prompt={teaching.prompt} retell={teaching.awaiting === "RETELL"} />
                </div>
              )
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
          className="hidden w-[24rem] shrink-0 overflow-y-auto border-l border-slate-200 bg-white p-4 lg:block"
        >
          {steps && <div className="mb-5 rounded-2xl bg-brand-50 p-3">{steps}</div>}
          <h2 className="font-semibold">Bản đồ bài học</h2>
          <p className="mb-3 text-sm text-slate-600">
            {teaching.passed}/{teaching.total} bài đã qua
          </p>
          {map}
        </aside>
      </div>
      <footer className="shrink-0 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)]">
        {state.lifecycle_state !== "COMPLETED" && <VoiceBar voice={voice} />}
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
            placeholder={
              teaching.awaiting === "RETELL" ? "Con nói lại bằng lời của con…" : "Con trả lời cô ở đây…"
            }
          />
        ) : (
          <p className="px-4 py-4 text-center text-base text-slate-700">Con chờ cô một chút nhé…</p>
        )}
      </footer>
    </div>
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
    <header className="border-b border-gold/25 bg-white">
      <div className="mx-auto flex items-center gap-3 px-4 py-3 lg:max-w-none">
        <Link to="/" aria-label="CAVAT, trang chủ" className="flex shrink-0 items-center gap-1.5 rounded-2xl">
          <Mascot size={40} />
          <span className="hidden font-extrabold text-brand-900 sm:inline">CAVAT</span>
        </Link>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-brand-800">
            {state.lifecycle_state === "COMPLETED"
              ? "Tổng kết"
              : [nodeName, step].filter(Boolean).join(" · ")}
          </p>
          <h1 className="truncate text-lg font-semibold">{teaching.chapter.title}</h1>
        </div>
        <p className="shrink-0 text-base font-medium">
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

/** The question the student answers in words: the end of a theory explanation, or the retell. */
function PromptCard({ prompt, retell }: { prompt: string; retell: boolean }) {
  return (
    <section
      aria-labelledby="prompt-title"
      className="rounded-2xl bg-white p-4 shadow-sm ring-2 ring-sky-200"
    >
      <h2 id="prompt-title" className="text-sm font-semibold text-sky-800">
        {retell ? "Con nói lại giúp cô" : "Cô hỏi con"}
      </h2>
      <p className="mt-1.5 text-lg leading-snug font-medium text-pretty md:text-xl">
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
