/** Read models of a mock session, all derived from its event log (the log is the source of truth). */
import {
  HINT_MOVES,
  type ChatTurn,
  type CurrentItem,
  type SessionState,
  type SessionSummary,
  type SessionTranscript,
  type TranscriptSegment,
  type TranscriptTurn,
} from "../contract";
import { allowedCommands, itemsDone, type MockEvent, type MockSession } from "./engine";
import { MOCK_PLAN, PLAN_ITEM_COUNT, findMisconception, lessonItem } from "./lesson";
import type { LessonPackage } from "./lessonTypes";
import { HINT_CHOICES } from "./phrases";

/** The conversation as the student sees it. */
export function chatTurns(session: MockSession): ChatTurn[] {
  const turns: ChatTurn[] = [];
  for (const event of session.events) {
    const base = {
      turn_id: event.event_id,
      sequence_no: event.sequence_no,
      item_attempt_id: event.item_attempt_id,
      occurred_at: event.occurred_at,
    };
    switch (event.event_type) {
      case "TUTOR_MESSAGE_SENT": {
        const { move, hint_level, text } = event.payload;
        const isHint = move !== null && HINT_MOVES.includes(move);
        turns.push({ ...base, actor: "tutor", text, move, hint_level: isHint ? hint_level : null });
        break;
      }
      case "ANSWER_SUBMITTED":
      case "EXPLANATION_SUBMITTED":
      case "HINT_REQUESTED":
      case "CHOICE_MADE":
        turns.push({ ...base, actor: "student", text: event.payload.text, move: null, hint_level: null });
        break;
    }
  }
  return turns;
}

function currentItem(session: MockSession, lesson: LessonPackage): CurrentItem | null {
  const loop = session.item;
  if (!loop) return null;
  const item = lessonItem(lesson, loop.item_id);
  const options =
    item.answer.type === "choice"
      ? (item.answer.options ?? []).map((option) => ({ id: option.id, text: option.text }))
      : [];
  return {
    item_attempt_id: loop.item_attempt_id,
    item_id: item.id,
    stem: item.stem,
    answer_format: item.answer.type,
    options,
    expecting: loop.phase === "VERIFYING" || loop.phase === "TEACH_BACK" ? "EXPLANATION" : "ANSWER",
    position: loop.position,
  };
}

export function toState(session: MockSession, lesson: LessonPackage): SessionState {
  const step = session.activity_index === null ? null : MOCK_PLAN[session.activity_index];
  return {
    session_id: session.session_id,
    state_version: session.state_version,
    lifecycle_state: session.lifecycle_state,
    lesson: { lesson_id: lesson.lesson_id, title: lesson.title },
    student_display_name: session.student_display_name,
    persona: lesson.persona,
    activity: step ? { activity_id: step.activity_id, type: step.type } : null,
    item: currentItem(session, lesson),
    pending_choice: session.item?.phase === "AWAITING_CHOICE" ? HINT_CHOICES.map((c) => ({ ...c })) : null,
    allowed_commands: allowedCommands(session),
    progress: { items_done: itemsDone(session), items_total: PLAN_ITEM_COUNT },
    transcript: chatTurns(session),
  };
}

export function toSummary(session: MockSession, lesson: LessonPackage): SessionSummary {
  const misconceptions = new Set<string>();
  for (const event of session.events) {
    if (event.event_type === "MISCONCEPTION_DETECTED") misconceptions.add(event.payload.misconception_id);
  }
  return {
    session_id: session.session_id,
    student_display_name: session.student_display_name,
    lesson_title: lesson.title,
    lifecycle_state: session.lifecycle_state,
    started_at: session.started_at,
    updated_at: session.updated_at,
    progress: { items_done: itemsDone(session), items_total: PLAN_ITEM_COUNT },
    misconception_ids: [...misconceptions],
    engine: "mock",
  };
}

function transcriptTurn(event: MockEvent, lesson: LessonPackage): TranscriptTurn | null {
  const base = { sequence_no: event.sequence_no, occurred_at: event.occurred_at };
  switch (event.event_type) {
    case "TUTOR_MESSAGE_SENT": {
      const { text, move, hint_level, hint_target, rule_ids, reason_codes } = event.payload;
      const tutor = move === null ? null : { move, hint_level, hint_target, rule_ids, reason_codes };
      return { ...base, actor: "tutor", text, tutor, student: null };
    }
    case "ANSWER_SUBMITTED": {
      const p = event.payload;
      const misconception = p.misconception_id
        ? {
            id: p.misconception_id,
            name: findMisconception(lesson, p.misconception_id)?.name ?? p.misconception_id,
            confidence: p.misconception_confidence ?? 0,
          }
        : null;
      const student = {
        kind: p.kind,
        outcome: p.outcome,
        normalized_answer: p.normalized_answer,
        misconception,
      };
      return { ...base, actor: "student", text: p.text, tutor: null, student };
    }
    case "EXPLANATION_SUBMITTED":
    case "HINT_REQUESTED":
    case "CHOICE_MADE": {
      const kind =
        event.event_type === "EXPLANATION_SUBMITTED"
          ? "EXPLANATION"
          : event.event_type === "HINT_REQUESTED"
            ? "HINT_REQUEST"
            : "CHOICE";
      const student = { kind, outcome: null, normalized_answer: null, misconception: null } as const;
      return { ...base, actor: "student", text: event.payload.text, tutor: null, student };
    }
    default:
      return null;
  }
}

type ItemSegment = Extract<TranscriptSegment, { kind: "item" }>;

/** The teacher's transcript: item blocks and session-level lines, in timeline order. */
export function toTranscript(session: MockSession, lesson: LessonPackage): SessionTranscript {
  const segments: TranscriptSegment[] = [];
  const items = new Map<string, ItemSegment>();

  for (const event of session.events) {
    const attemptId = event.item_attempt_id;
    if (event.event_type === "QUESTION_SHOWN" && attemptId) {
      const block: ItemSegment = {
        kind: "item",
        item_attempt_id: attemptId,
        item_id: event.payload.item_id,
        activity_type: event.payload.activity_type,
        stem: event.payload.stem,
        position: event.payload.position,
        resolution: null,
        max_hint_level: 0,
        turns: [],
      };
      items.set(attemptId, block);
      segments.push(block);
      continue;
    }
    const block = attemptId ? items.get(attemptId) : undefined;
    if (block && event.event_type === "HINT_DELIVERED") {
      if (event.payload.hint_level > block.max_hint_level) block.max_hint_level = event.payload.hint_level;
    }
    if (block && event.event_type === "ITEM_RESOLVED") {
      block.resolution = event.payload.resolution;
      block.max_hint_level = event.payload.max_hint_level;
    }
    const turn = transcriptTurn(event, lesson);
    if (!turn) continue;
    if (block) {
      block.turns.push(turn);
      continue;
    }
    const last = segments.at(-1);
    if (last?.kind === "session") last.turns.push(turn);
    else segments.push({ kind: "session", turns: [turn] });
  }
  return { session: toSummary(session, lesson), segments };
}
