import type {
  ItemResolution,
  SessionTranscript,
  StudentAnnotation,
  TeachAnnotation,
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
  RULE_LABEL,
  CONDUCTED_LABEL,
  STUDENT_KIND_LABEL,
  TEACH_KIND_LABEL,
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
              {session.progress.items_done}/{session.progress.items_total}{" "}
              {session.mode === "CHAPTER" ? "bài đã qua" : "câu"}
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
          <span className={`font-semibold ${tutor ? "text-brand-800" : "text-sky-800"}`}>
            {tutor ? "Tutor" : studentName}:
          </span>{" "}
          <MathText text={turn.text} />
        </p>
        {turn.tutor && <TutorChips annotation={turn.tutor} />}
        {turn.teach && <TeachChips annotation={turn.teach} />}
        {turn.student && <StudentChips annotation={turn.student} />}
      </div>
    </li>
  );
}

function TutorChips({ annotation }: { annotation: TutorAnnotation }) {
  const { move, hint_level, hint_target, rule_ids, source, chosen } = annotation;
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
      {chosen && (
        <Chip
          tone="sky"
          title={`Policy cho phép: ${chosen.options.map((m) => MOVE_LABEL[m] ?? m).join(", ")}`}
        >
          {chosen.accepted
            ? `Qwen chọn nước này${chosen.reason ? `: ${chosen.reason}` : ""}`
            : "Qwen chọn nước ngoài danh sách, policy giữ nước của mình"}
        </Chip>
      )}
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

const SOURCE_LABEL: Record<NonNullable<TeachAnnotation["source"]>, string> = {
  TEMPLATE: "Câu mẫu đã duyệt",
  LLM: "Qwen viết, đã kiểm chứng với nguồn",
  EXTRACT: "Trích nguyên văn đoạn nguồn",
  WEB: "Tra Wikipedia tiếng Việt (tài liệu chưa có), đã kiểm chứng với bài viết",
};

/** CTX-1: what an unclear message of the child was read as (tutor/reader.py LABELS). */
const READ_LABEL: Record<string, string> = {
  ANSWER: "con trả lời",
  ASKS_ABOUT: "con hỏi về",
  ASK_TASK: "con chưa hiểu đề",
  DONT_KNOW: "con không biết",
  OFF_TOPIC: "chuyện ngoài bài",
  AFFECT: "con đang chán hoặc buồn",
  OTHER: "chưa rõ",
};

const PARKED_LABEL: Record<NonNullable<TeachAnnotation["parked"]>, string> = {
  NOT_GROUNDED: "Tài liệu và nguồn tra cứu chưa trả lời được: để lại cho giáo viên",
  SAME_AS_CHECK: "Con hỏi lại câu của cô: mời con tự nghĩ",
  LIMIT: "Quá số câu hỏi một lượt: để lại cho giáo viên",
  LATER: "Thuộc bài học sau: không dạy trước",
};

/** A message of the teaching loop and the node decision behind it (chapter sessions). */
function TeachChips({ annotation }: { annotation: TeachAnnotation }) {
  const { source = "TEMPLATE", sources = [], rejected = [], grounded, grounding, parked } = annotation;
  return (
    <div className="flex flex-col gap-1">
      <p className="flex flex-wrap gap-1">
        <Chip tone="teal">{TEACH_KIND_LABEL[annotation.kind]}</Chip>
        {annotation.rule_ids.map((rule) => (
          <Chip key={rule} mono title={RULE_LABEL[rule]}>
            {rule}
          </Chip>
        ))}
        {annotation.reason_codes.map((code) => (
          <Chip key={code} mono>
            {code}
          </Chip>
        ))}
        {source !== "TEMPLATE" && <Chip tone="sky">{SOURCE_LABEL[source]}</Chip>}
        {grounded != null && (
          <Chip tone={grounded ? "emerald" : "amber"} title={grounding ?? undefined}>
            {grounded ? "Có căn cứ" : "Không có căn cứ"}
            {grounding ? ` (${grounding})` : ""}
          </Chip>
        )}
        {parked && <Chip tone="amber">{PARKED_LABEL[parked]}</Chip>}
        {rejected.length > 0 && (
          <Chip tone="rose" title={rejected.map((codes) => codes.join(", ")).join(" · ")}>
            Qwen bị chặn {rejected.length} lần: {rejected.flat().join(", ")}
          </Chip>
        )}
      </p>
      {sources.length > 0 && <p className="text-xs text-slate-600">Nguồn: {sources.join(" · ")}</p>}
    </div>
  );
}

function StudentChips({ annotation }: { annotation: StudentAnnotation }) {
  const { kind, outcome, normalized_answer, misconception, retell } = annotation;
  const outcomeTone: ChipTone = outcome === "CORRECT" ? "emerald" : outcome === "WRONG" ? "rose" : "slate";
  return (
    <p className="flex flex-wrap gap-1">
      <Chip>{STUDENT_KIND_LABEL[kind]}</Chip>
      {annotation.safety && <Chip tone="rose">Đáng lo: cô cần đọc kỹ câu này</Chip>}
      {annotation.voice && (
        <Chip tone="sky" title="Lời bé nói, máy nghe thành chữ (chế độ nói chuyện)">
          Bé nói
        </Chip>
      )}
      {annotation.conducted && annotation.conducted.signals.length > 0 && (
        <Chip tone="amber" title={`Bé gõ: ${annotation.conducted.raw}`}>
          Bé gõ «{annotation.conducted.raw}» ·{" "}
          {annotation.conducted.signals.map((s) => CONDUCTED_LABEL[s] ?? s).join(", ")}
        </Chip>
      )}
      {annotation.read && (
        <Chip tone="sky" title={annotation.read.source === "LLM" ? "Qwen đọc câu này" : "Đọc bằng luật"}>
          Gia sư hiểu: {READ_LABEL[annotation.read.label] ?? annotation.read.label}
          {annotation.read.focus ? ` «${annotation.read.focus}»` : ""}
          {annotation.read.source === "LLM" ? " (Qwen đọc)" : ""}
        </Chip>
      )}
      {outcome && <Chip tone={outcomeTone}>{OUTCOME_LABEL[outcome]}</Chip>}
      {kind === "ANSWER" && outcome === null && <Chip>Chưa chấm</Chip>}
      {normalized_answer && (
        <Chip tone="sky">
          Đọc là:&nbsp;
          <MathText text={normalized_answer} />
        </Chip>
      )}
      {retell && (
        <Chip tone={retell.score >= 0.5 ? "emerald" : "rose"} title="Số ý bắt buộc con nói được">
          {`${retell.purpose === "RECALL" ? "Nhớ lại bài cũ" : "Nói lại"}: ${retell.ideas_found}/${retell.ideas_total} ý`}
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
