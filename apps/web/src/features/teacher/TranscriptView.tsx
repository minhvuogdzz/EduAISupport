import type {
  ItemResolution,
  SessionTranscript,
  StudentAnnotation,
  TranscriptItem,
  TranscriptTurn,
  TutorAnnotation,
} from "../../api/contract";
import { Chip, type ChipTone } from "../../components/Chip";
import {
  ACTIVITY_LABEL,
  HINT_LEVEL_LABEL,
  HINT_TARGET_LABEL,
  MOVE_LABEL,
  OUTCOME_LABEL,
  RESOLUTION_LABEL,
  STUDENT_KIND_LABEL,
} from "../../components/labels";
import { MathText } from "../../components/MathText";
import { formatViDateTime, formatViDecimal, formatViTime } from "../../lib/viNumber";
import { LifecycleChip } from "./SessionList";

const RESOLUTION_TONE: Record<ItemResolution, ChipTone> = {
  INDEPENDENT: "emerald",
  SUPPORTED: "sky",
  WORKED: "amber",
  UNRESOLVED: "rose",
};

/** Transcript of one session for the teacher: every turn with the decision behind it (PART 13.3). */
export function TranscriptView({ transcript }: { transcript: SessionTranscript }) {
  const { session, segments } = transcript;
  const lastItemIndex = segments.findLastIndex((segment) => segment.kind === "item");
  return (
    <article aria-labelledby="transcript-title" className="flex flex-col gap-4">
      <header className="flex flex-col gap-1 rounded-2xl bg-white p-4 ring-1 ring-slate-200">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="transcript-title" className="text-2xl font-semibold">
            {session.student_display_name}
          </h2>
          <LifecycleChip state={session.lifecycle_state} />
          {session.engine === "mock" && <Chip tone="amber">Dữ liệu giả lập</Chip>}
        </div>
        <p className="text-slate-700">{session.lesson_title}</p>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-700">
          <div>
            <dt className="inline">Bắt đầu: </dt>
            <dd className="inline">
              {session.started_at ? formatViDateTime(session.started_at) : "chưa bắt đầu"}
            </dd>
          </div>
          <div>
            <dt className="inline">Tiến độ: </dt>
            <dd className="inline">
              {session.progress.items_done}/{session.progress.items_total} câu
            </dd>
          </div>
          <div>
            <dt className="inline">Misconception: </dt>
            <dd className="inline font-mono">{session.misconception_ids.join(", ") || "không có"}</dd>
          </div>
        </dl>
      </header>

      {segments.map((segment, index) =>
        segment.kind === "item" ? (
          <ItemBlock
            key={segment.item_attempt_id}
            item={segment}
            studentName={session.student_display_name}
            inProgress={session.lifecycle_state === "ACTIVE" && index === lastItemIndex}
          />
        ) : (
          <ol
            key={`session-${index}`}
            aria-label="Lời mở đầu, chuyển hoạt động, tổng kết"
            className="rounded-2xl border border-dashed border-slate-300 px-4"
          >
            {segment.turns.map((turn) => (
              <TurnRow key={turn.sequence_no} turn={turn} studentName={session.student_display_name} />
            ))}
          </ol>
        ),
      )}
    </article>
  );
}

function ItemBlock({
  item,
  studentName,
  inProgress,
}: {
  item: TranscriptItem;
  studentName: string;
  inProgress: boolean;
}) {
  const titleId = `item-${item.item_attempt_id}`;
  return (
    <section aria-labelledby={titleId} className="rounded-2xl bg-white ring-1 ring-slate-200">
      <header className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-3">
        <h3 id={titleId} className="font-semibold">
          Câu {item.position} · <span className="font-mono">{item.item_id}</span>
        </h3>
        <Chip>{ACTIVITY_LABEL[item.activity_type]}</Chip>
        {item.resolution ? (
          <Chip tone={RESOLUTION_TONE[item.resolution]} title={item.resolution}>
            {RESOLUTION_LABEL[item.resolution]}
          </Chip>
        ) : (
          <Chip>{inProgress ? "Đang làm" : "Chưa chấm"}</Chip>
        )}
        <span className="text-sm text-slate-600">
          Gợi ý cao nhất: H{item.max_hint_level} ({HINT_LEVEL_LABEL[item.max_hint_level]})
        </span>
      </header>
      <p className="px-4 pt-3 text-lg">
        <MathText text={item.stem} />
      </p>
      <ol className="divide-y divide-slate-100 px-4 pb-1">
        {item.turns.map((turn) => (
          <TurnRow key={turn.sequence_no} turn={turn} studentName={studentName} />
        ))}
      </ol>
    </section>
  );
}

function TurnRow({ turn, studentName }: { turn: TranscriptTurn; studentName: string }) {
  const tutor = turn.actor === "tutor";
  return (
    <li className="grid grid-cols-[4.5rem_1fr] gap-3 py-2">
      <time dateTime={turn.occurred_at} className="pt-1 font-mono text-xs text-slate-500">
        {formatViTime(turn.occurred_at)}
      </time>
      <div className="flex flex-col gap-1">
        <p>
          <span className={`font-semibold ${tutor ? "text-teal-800" : "text-sky-800"}`}>
            {tutor ? "Tutor" : studentName}:
          </span>{" "}
          <MathText text={turn.text} />
        </p>
        {turn.tutor && <TutorChips annotation={turn.tutor} />}
        {turn.student && <StudentChips annotation={turn.student} />}
      </div>
    </li>
  );
}

function TutorChips({ annotation }: { annotation: TutorAnnotation }) {
  const { move, hint_level, hint_target, rule_ids, source } = annotation;
  return (
    <p className="flex flex-wrap gap-1">
      <Chip tone="teal" title={move}>
        {MOVE_LABEL[move]}
      </Chip>
      {hint_level !== null && (
        <Chip tone="amber" title={HINT_LEVEL_LABEL[hint_level]}>
          H{hint_level}
          {hint_target ? ` · ${HINT_TARGET_LABEL[hint_target]}` : ""}
        </Chip>
      )}
      {hint_level === null && hint_target && <Chip>{HINT_TARGET_LABEL[hint_target]}</Chip>}
      {rule_ids.map((rule) => (
        <Chip key={rule} mono>
          {rule}
        </Chip>
      ))}
      {source === "LLM" && (
        <Chip tone="sky" title="AI chỉ diễn đạt nước đi do policy chọn; câu đã qua bộ kiểm tra">
          AI diễn đạt
        </Chip>
      )}
      {source === "FALLBACK" && (
        <Chip
          tone="rose"
          title="Bài không có câu đã duyệt cho lượt này, hoặc câu sinh ra không qua bộ kiểm tra"
        >
          Câu dự phòng
        </Chip>
      )}
    </p>
  );
}

function StudentChips({ annotation }: { annotation: StudentAnnotation }) {
  const { kind, outcome, normalized_answer, misconception } = annotation;
  const outcomeTone: ChipTone = outcome === "CORRECT" ? "emerald" : outcome === "WRONG" ? "rose" : "slate";
  return (
    <p className="flex flex-wrap gap-1">
      <Chip>{STUDENT_KIND_LABEL[kind]}</Chip>
      {outcome && <Chip tone={outcomeTone}>{OUTCOME_LABEL[outcome]}</Chip>}
      {kind === "ANSWER" && outcome === null && <Chip>Chưa chấm</Chip>}
      {normalized_answer && (
        <Chip tone="sky">
          Đọc là:&nbsp;
          <MathText text={normalized_answer} />
        </Chip>
      )}
      {misconception && (
        <Chip tone="rose" title={`Độ tin cậy ${formatViDecimal(misconception.confidence)}`}>
          {misconception.id} · {misconception.name} ({formatViDecimal(misconception.confidence)})
        </Chip>
      )}
    </p>
  );
}
