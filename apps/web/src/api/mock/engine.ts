/**
 * MOCK ONLY: a small item loop so the screens can run before the real tutor runtime exists.
 *
 * It follows the real design closely enough to exercise every UI state — rule ids of blueprint PART 15.2,
 * the item loop of PART 16.2, the event envelope of PART 10.3 — but it is NOT the tutor policy (T02),
 * the renderer (T03) or the item loop (T04). Rule ids starting with "MOCK-" mark behaviour that only
 * exists here. State and events of a session live in one record that is written as a whole, like a
 * learning_sessions document on Atlas M0 (CLAUDE.md, design rule 10).
 */
import {
  HINT_MOVES,
  type ActivityType,
  type ActorType,
  type CommandType,
  type HintLevel,
  type HintTarget,
  type ItemResolution,
  type LifecycleState,
  type Modality,
  type Move,
  type Outcome,
  type ResponseKind,
} from "../contract";
import { checkAnswer, type MockCheck } from "./checker";
import { MOCK_PLAN, findMisconception, hintCap, lessonItem, siblingOf } from "./lesson";
import type { LessonItem, LessonPackage, Misconception, OpenItem } from "./lessonTypes";
import { HINT_CHOICES, PHRASES } from "./phrases";

/** Every learner record carries a school_id (CLAUDE.md, design rule 5). */
export const DEMO_SCHOOL_ID = "demo-school";

const MISCONCEPTION_THRESHOLD = 0.7; // T02: a misconception counts as clear from 0.7
const FRUSTRATION_WRONG_ANSWERS = 3; // T02: frustration after 3 turns without progress

export type ItemPhase = "AWAITING" | "AWAITING_CHOICE" | "VERIFYING" | "TEACH_BACK";

export interface ItemLoop {
  item_attempt_id: string;
  item_id: string;
  position: number;
  phase: ItemPhase;
  attempts: number;
  wrong_answers: number;
  max_hint_level: HintLevel;
  hint_requests: number;
  misconception_handled: boolean;
}

export type HintSource =
  | "item_template"
  | "generic_template"
  | "counter_example"
  | "similar_example"
  | "worked_solution"
  | "explanation";

export interface EventPayloads {
  SESSION_STARTED: Record<string, never>;
  ACTIVITY_STARTED: { activity_type: ActivityType };
  ACTIVITY_COMPLETED: { activity_type: ActivityType };
  QUESTION_SHOWN: { item_id: string; activity_type: ActivityType; stem: string; position: number };
  ANSWER_SUBMITTED: {
    text: string;
    kind: ResponseKind;
    modality: Modality;
    attempt_no: number;
    outcome: Outcome | null;
    normalized_answer: string | null;
    misconception_id: string | null;
    misconception_confidence: number | null;
  };
  EXPLANATION_SUBMITTED: { text: string; modality: Modality };
  HINT_REQUESTED: { text: string };
  /** Micro choices are logged (PART 24.3) but PART 10.4 has no event type for them yet. */
  CHOICE_MADE: { choice_id: string; text: string };
  MISCONCEPTION_DETECTED: { misconception_id: string; confidence: number };
  POLICY_DECISION: {
    move: Move;
    hint_level: HintLevel | null;
    hint_target: HintTarget | null;
    rule_ids: string[];
    reason_codes: string[];
  };
  HINT_DELIVERED: { hint_level: HintLevel; hint_target: HintTarget | null; source: HintSource };
  /** move is null for scripted lines outside the policy: greeting, activity intros, summary. */
  TUTOR_MESSAGE_SENT: {
    text: string;
    move: Move | null;
    hint_level: HintLevel | null;
    hint_target: HintTarget | null;
    rule_ids: string[];
    reason_codes: string[];
  };
  ITEM_RESOLVED: { item_id: string; resolution: ItemResolution | null; max_hint_level: HintLevel };
  SESSION_COMPLETED: { items_done: number };
}
export type EventType = keyof EventPayloads;

/** PART 10.3 envelope, reduced to what the mock needs. */
interface Envelope<T extends EventType> {
  event_id: string;
  event_type: T;
  schema_version: 1;
  occurred_at: string;
  school_id: string;
  student_id: string;
  session_id: string;
  activity_id: string | null;
  item_attempt_id: string | null;
  sequence_no: number;
  actor: { type: ActorType; id: string | null };
  correlation: { tutor_run_id: string };
  idempotency_key: string | null;
  payload: EventPayloads[T];
}
export type MockEvent = { [T in EventType]: Envelope<T> }[EventType];

export interface MockSession {
  session_id: string;
  school_id: string;
  student_id: string;
  student_display_name: string;
  lifecycle_state: LifecycleState;
  state_version: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  /** Index into MOCK_PLAN; null before the session starts. */
  activity_index: number | null;
  item_index: number;
  item: ItemLoop | null;
  /** Append-only event log of the session (sequence_no = index + 1). */
  events: MockEvent[];
}

export interface EngineContext {
  lesson: LessonPackage;
  now: () => Date;
  newId: () => string;
}

export type MockCommand =
  | { type: "ANSWER"; kind: ResponseKind; text: string; modality: Modality }
  | { type: "HINT_REQUEST" }
  | { type: "CHOICE"; choice_id: string };
type AnswerCommand = Extract<MockCommand, { type: "ANSWER" }>;

export function resolutionFor(level: HintLevel): ItemResolution {
  if (level === 0) return "INDEPENDENT";
  return level <= 5 ? "SUPPORTED" : "WORKED";
}

export function newSession(ctx: EngineContext, studentDisplayName: string): MockSession {
  const now = ctx.now().toISOString();
  return {
    session_id: ctx.newId(),
    school_id: DEMO_SCHOOL_ID,
    student_id: ctx.newId(),
    student_display_name: studentDisplayName,
    lifecycle_state: "READY",
    state_version: 1,
    created_at: now,
    updated_at: now,
    started_at: null,
    activity_index: null,
    item_index: 0,
    item: null,
    events: [],
  };
}

export function allowedCommands(session: MockSession): CommandType[] {
  if (session.lifecycle_state !== "ACTIVE" || !session.item) return [];
  switch (session.item.phase) {
    case "AWAITING":
      return ["ANSWER", "HINT_REQUEST"];
    case "AWAITING_CHOICE":
      return ["ANSWER", "CHOICE"];
    case "VERIFYING":
    case "TEACH_BACK":
      return ["ANSWER"];
  }
}

// ---------------------------------------------------------------- one command = one run

interface Decision {
  hint_level?: HintLevel;
  hint_target?: HintTarget;
  rule_ids?: string[];
  reason_codes?: string[];
  source?: HintSource;
}

function openRun(ctx: EngineContext, s: MockSession, idempotencyKey: string | null) {
  const runId = ctx.newId();
  const tutorTurnIds: string[] = [];

  function emit<T extends EventType>(type: T, payload: EventPayloads[T], actor: ActorType): string {
    const eventId = ctx.newId();
    const activity = s.activity_index === null ? null : MOCK_PLAN[s.activity_index];
    s.events.push({
      event_id: eventId,
      event_type: type,
      schema_version: 1,
      occurred_at: ctx.now().toISOString(),
      school_id: s.school_id,
      student_id: s.student_id,
      session_id: s.session_id,
      activity_id: activity?.activity_id ?? null,
      item_attempt_id: s.item?.item_attempt_id ?? null,
      sequence_no: s.events.length + 1,
      actor: { type: actor, id: actor === "student" ? s.student_id : null },
      correlation: { tutor_run_id: runId },
      idempotency_key: idempotencyKey,
      payload,
    } as MockEvent);
    return eventId;
  }

  /** A tutor turn chosen by the (mock) policy. */
  function say(move: Move, text: string, decision: Decision = {}) {
    const hint_level = decision.hint_level ?? null;
    const hint_target = decision.hint_target ?? null;
    const rule_ids = decision.rule_ids ?? [];
    const reason_codes = decision.reason_codes ?? [];
    emit("POLICY_DECISION", { move, hint_level, hint_target, rule_ids, reason_codes }, "system");
    if (hint_level !== null && HINT_MOVES.includes(move)) {
      emit(
        "HINT_DELIVERED",
        { hint_level, hint_target, source: decision.source ?? "item_template" },
        "system",
      );
      if (s.item && hint_level > s.item.max_hint_level) s.item.max_hint_level = hint_level;
    }
    const payload = { text, move, hint_level, hint_target, rule_ids, reason_codes };
    tutorTurnIds.push(emit("TUTOR_MESSAGE_SENT", payload, "tutor"));
  }

  /** A scripted line outside the policy (greeting, activity intro, summary). */
  function script(text: string) {
    const payload = { text, move: null, hint_level: null, hint_target: null, rule_ids: [], reason_codes: [] };
    tutorTurnIds.push(emit("TUTOR_MESSAGE_SENT", payload, "tutor"));
  }

  return { emit, say, script, tutorTurnIds };
}

interface Flow {
  ctx: EngineContext;
  s: MockSession;
  run: ReturnType<typeof openRun>;
}

function touch(ctx: EngineContext, s: MockSession) {
  s.state_version += 1;
  s.updated_at = ctx.now().toISOString();
}

/** READY → ACTIVE: greeting, first activity, first question. Returns the new tutor turn ids. */
export function startSession(ctx: EngineContext, s: MockSession): string[] {
  const run = openRun(ctx, s, null);
  s.lifecycle_state = "ACTIVE";
  s.started_at = ctx.now().toISOString();
  run.emit("SESSION_STARTED", {}, "student");
  run.script(PHRASES.greeting(s.student_display_name, ctx.lesson.title));
  enterActivity({ ctx, s, run }, 0);
  touch(ctx, s);
  return run.tutorTurnIds;
}

/** Applies one validated student command to `s` (mutated). Returns the new tutor turn ids. */
export function applyCommand(
  ctx: EngineContext,
  s: MockSession,
  command: MockCommand,
  idempotencyKey: string | null,
): string[] {
  const loop = s.item;
  if (!loop || s.activity_index === null) throw new Error("no open item: validate commands first");
  const run = openRun(ctx, s, idempotencyKey);
  const flow: Flow = { ctx, s, run };
  const item = lessonItem(ctx.lesson, loop.item_id);
  const activity = MOCK_PLAN[s.activity_index].type;
  switch (command.type) {
    case "ANSWER":
      onAnswer(flow, loop, item, activity, command);
      break;
    case "HINT_REQUEST":
      run.emit("HINT_REQUESTED", { text: PHRASES.hintRequest }, "student");
      onHelp(flow, loop, item, activity);
      break;
    case "CHOICE":
      onChoice(flow, loop, openItem(item), activity, command.choice_id);
      break;
  }
  touch(ctx, s);
  return run.tutorTurnIds;
}

// ---------------------------------------------------------------- plan navigation

function positionOf(s: MockSession): number {
  let position = s.item_index + 1;
  for (let i = 0; i < (s.activity_index ?? 0); i++) position += MOCK_PLAN[i].item_ids.length;
  return position;
}

export function itemsDone(s: MockSession): number {
  return s.events.filter((e) => e.event_type === "ITEM_RESOLVED").length;
}

function presentItem(f: Flow) {
  const step = MOCK_PLAN[f.s.activity_index ?? 0];
  const item = lessonItem(f.ctx.lesson, step.item_ids[f.s.item_index]);
  f.s.item = {
    item_attempt_id: f.ctx.newId(),
    item_id: item.id,
    position: positionOf(f.s),
    phase: "AWAITING",
    attempts: 0,
    wrong_answers: 0,
    max_hint_level: 0,
    hint_requests: 0,
    misconception_handled: false,
  };
  f.run.emit(
    "QUESTION_SHOWN",
    { item_id: item.id, activity_type: step.type, stem: item.stem, position: f.s.item.position },
    "system",
  );
  f.run.say("PRESENT", item.stem);
}

function enterActivity(f: Flow, index: number) {
  const step = MOCK_PLAN[index];
  f.s.activity_index = index;
  f.s.item_index = 0;
  f.s.item = null;
  f.run.emit("ACTIVITY_STARTED", { activity_type: step.type }, "system");
  if (step.type === "SUMMARY") {
    finish(f);
    return;
  }
  const intro = PHRASES.activityIntro[step.type];
  if (intro) f.run.script(intro);
  presentItem(f);
}

function closeItem(f: Flow, loop: ItemLoop, resolution: ItemResolution | null) {
  f.run.emit(
    "ITEM_RESOLVED",
    { item_id: loop.item_id, resolution, max_hint_level: loop.max_hint_level },
    "system",
  );
  const index = f.s.activity_index ?? 0;
  const step = MOCK_PLAN[index];
  f.s.item = null;
  if (f.s.item_index + 1 < step.item_ids.length) {
    f.s.item_index += 1;
    presentItem(f);
    return;
  }
  f.run.emit("ACTIVITY_COMPLETED", { activity_type: step.type }, "system");
  enterActivity(f, index + 1);
}

function finish(f: Flow) {
  const done = itemsDone(f.s);
  f.run.script(PHRASES.summary(done));
  f.run.emit("ACTIVITY_COMPLETED", { activity_type: "SUMMARY" }, "system");
  f.run.emit("SESSION_COMPLETED", { items_done: done }, "system");
  f.s.lifecycle_state = "COMPLETED";
}

// ---------------------------------------------------------------- the mock policy

function openItem(item: LessonItem): OpenItem {
  if (item.purpose === "EXIT") throw new Error(`${item.id} is sealed: the mock cannot tutor it`);
  return item;
}

interface PickedHint {
  level: HintLevel;
  target: HintTarget;
  text: string;
  source: HintSource;
}

/** The item's own template at `level`, else the lesson's generic one (T03 order, simplified). */
function hintAt(lesson: LessonPackage, item: LessonItem, level: HintLevel): PickedHint | undefined {
  const own = item.hints.find((h) => h.level === level);
  if (own) return { ...own, source: "item_template" };
  const generic = lesson.generic_hints.find((h) => h.level === level);
  return generic ? { ...generic, source: "generic_template" } : undefined;
}

function counterExample(misconception: Misconception, item: OpenItem): string | null {
  if (item.answer.type !== "compare") return null;
  const { left, right } = item.answer;
  const template = misconception.counter_examples.find((t) => t.includes("{left}") || t.includes("{right}"));
  return template ? template.replaceAll("{left}", left).replaceAll("{right}", right) : null;
}

function onAnswer(f: Flow, loop: ItemLoop, item: LessonItem, activity: ActivityType, command: AnswerCommand) {
  const { run } = f;
  if (loop.phase === "VERIFYING" || loop.phase === "TEACH_BACK") {
    run.emit("EXPLANATION_SUBMITTED", { text: command.text, modality: command.modality }, "student");
    run.say("CLOSE_ITEM", PHRASES.thanksForExplaining, {
      rule_ids: [loop.phase === "TEACH_BACK" ? "R-TEACH-BACK" : "R-VERIFY"],
      reason_codes: ["EXPLANATION_RECEIVED"],
    });
    closeItem(f, loop, resolutionFor(loop.max_hint_level));
    return;
  }
  loop.phase = "AWAITING"; // answering also dismisses a pending micro choice
  const submitted = { text: command.text, kind: command.kind, modality: command.modality };

  if (item.purpose === "EXIT") {
    // Sealed at build time: grading an EXIT item is the server's job only.
    loop.attempts += 1;
    run.emit(
      "ANSWER_SUBMITTED",
      {
        ...submitted,
        attempt_no: loop.attempts,
        outcome: null,
        normalized_answer: null,
        misconception_id: null,
        misconception_confidence: null,
      },
      "student",
    );
    run.say("CLOSE_ITEM", PHRASES.answerRecorded, {
      rule_ids: ["MOCK-EXIT-RECORD"],
      reason_codes: ["NOT_GRADED_IN_MOCK"],
    });
    closeItem(f, loop, null);
    return;
  }

  const result = checkAnswer(item.answer, command.text);
  if (result.outcome === "CORRECT" || result.outcome === "WRONG") loop.attempts += 1;
  run.emit(
    "ANSWER_SUBMITTED",
    {
      ...submitted,
      attempt_no: loop.attempts,
      outcome: result.outcome,
      normalized_answer: result.normalized,
      misconception_id: result.misconception_id,
      misconception_confidence: result.misconception_id ? result.confidence : null,
    },
    "student",
  );
  if (result.misconception_id) {
    run.emit(
      "MISCONCEPTION_DETECTED",
      { misconception_id: result.misconception_id, confidence: result.confidence },
      "system",
    );
  }

  switch (result.outcome) {
    case "CORRECT":
      onCorrect(f, loop, item);
      return;
    case "WRONG":
      onWrong(f, loop, item, activity, result);
      return;
    case "HELP_REQUEST":
    case "ANSWER_DEMAND":
      onHelp(f, loop, item, activity);
      return;
    case "NO_RESPONSE":
      run.say("NUDGE", item.rephrase ?? PHRASES.nudge, {
        hint_target: "TASK",
        rule_ids: ["R-NO-RESPONSE"],
        reason_codes: ["NO_RESPONSE"],
      });
      return;
    case "NEEDS_LLM":
      run.say("CLOSE_ITEM", PHRASES.answerRecorded, {
        rule_ids: ["MOCK-OPEN-RECORD"],
        reason_codes: ["NOT_GRADED_IN_MOCK"],
      });
      closeItem(f, loop, null);
      return;
    default:
      run.say("REDIRECT", item.rephrase ?? PHRASES.redirect, {
        hint_target: "TASK",
        rule_ids: ["R-REDIRECT"],
        reason_codes: [result.outcome],
      });
  }
}

function onCorrect(f: Flow, loop: ItemLoop, item: OpenItem) {
  if (loop.max_hint_level >= 6) {
    loop.phase = "TEACH_BACK";
    f.run.say("TEACH_BACK", PHRASES.teachBack, {
      rule_ids: ["R-CORRECT", "R-TEACH-BACK"],
      reason_codes: ["ANSWER_CORRECT", "AFTER_WORKED_GUIDANCE"],
    });
    return;
  }
  if (item.verify_prompt) {
    loop.phase = "VERIFYING";
    f.run.say("VERIFY", item.verify_prompt, {
      rule_ids: ["R-CORRECT", "R-VERIFY"],
      reason_codes: ["ANSWER_CORRECT"],
    });
    return;
  }
  f.run.say("CONFIRM_ADVANCE", PHRASES.correct, {
    rule_ids: ["R-CORRECT"],
    reason_codes: ["ANSWER_CORRECT"],
  });
  closeItem(f, loop, resolutionFor(loop.max_hint_level));
}

function onWrong(f: Flow, loop: ItemLoop, item: OpenItem, activity: ActivityType, result: MockCheck) {
  loop.wrong_answers += 1;
  const reasons = ["ANSWER_WRONG"];
  const misconception =
    result.misconception_id && result.confidence >= MISCONCEPTION_THRESHOLD
      ? findMisconception(f.ctx.lesson, result.misconception_id)
      : undefined;
  if (misconception && !loop.misconception_handled) {
    loop.misconception_handled = true;
    reasons.push(`MISCONCEPTION:${misconception.id}`);
    const level = Math.min(hintCap(activity), Math.max(2, loop.max_hint_level)) as HintLevel;
    const counter = counterExample(misconception, item);
    if (counter) {
      f.run.say("COGNITIVE_CONFLICT", counter, {
        hint_level: level,
        hint_target: "CONCEPT",
        rule_ids: ["R-MISC-HIGH"],
        reason_codes: reasons,
        source: "counter_example",
      });
      return;
    }
    const hint = level > loop.max_hint_level ? hintAt(f.ctx.lesson, item, level) : undefined;
    if (hint) {
      f.run.say("HINT", hint.text, {
        hint_level: hint.level,
        hint_target: hint.target,
        rule_ids: ["R-MISC-HIGH"],
        reason_codes: reasons,
        source: hint.source,
      });
      return;
    }
  }
  if (loop.wrong_answers === 1 && loop.max_hint_level === 0) {
    f.run.say("PROBE", PHRASES.probe, { rule_ids: ["R-FIRST-WRONG"], reason_codes: reasons });
    return;
  }
  escalate(f, loop, item, activity, "R-ESCALATE", reasons);
}

function onHelp(f: Flow, loop: ItemLoop, item: LessonItem, activity: ActivityType) {
  loop.hint_requests += 1;
  const reasons = ["HELP_REQUESTED"];
  if (item.purpose === "EXIT") {
    const hint = loop.max_hint_level < 1 ? hintAt(f.ctx.lesson, item, 1) : undefined;
    if (hint) {
      f.run.say("HINT", hint.text, {
        hint_level: 1,
        hint_target: hint.target,
        rule_ids: ["R-ASSESS-CAP"],
        reason_codes: reasons,
        source: hint.source,
      });
    } else {
      f.run.say("NUDGE", PHRASES.assessmentNoMoreHints, {
        rule_ids: ["R-ASSESS-CAP"],
        reason_codes: [...reasons, "HINT_CAP_REACHED"],
      });
    }
    return;
  }
  if (loop.hint_requests === 1) {
    loop.phase = "AWAITING_CHOICE";
    f.run.say("OFFER_CHOICE", PHRASES.offerChoice, { rule_ids: ["R-HELP-REQUEST"], reason_codes: reasons });
    return;
  }
  escalate(f, loop, item, activity, "R-HELP-REQUEST", reasons);
}

function onChoice(f: Flow, loop: ItemLoop, item: OpenItem, activity: ActivityType, choiceId: string) {
  const choice = HINT_CHOICES.find((c) => c.choice_id === choiceId);
  if (!choice) throw new Error(`unknown choice ${choiceId}: validate commands first`);
  f.run.emit("CHOICE_MADE", { choice_id: choice.choice_id, text: choice.label }, "student");
  loop.phase = "AWAITING";
  const reasons = ["HELP_REQUESTED", `CHOSE:${choice.choice_id}`];
  if (choice.choice_id === "EXAMPLE") {
    const example = siblingOf(f.ctx.lesson, item)?.worked_solution ?? [];
    const level = Math.min(hintCap(activity), Math.max(3, loop.max_hint_level + 1)) as HintLevel;
    if (example.length >= 2 && level > loop.max_hint_level) {
      f.run.say("HINT", PHRASES.similarExample(example), {
        hint_level: level,
        hint_target: "STRATEGY",
        rule_ids: ["R-HELP-REQUEST"],
        reason_codes: reasons,
        source: "similar_example",
      });
      return;
    }
  }
  escalate(f, loop, item, activity, "R-HELP-REQUEST", reasons);
}

/** Next rung of the ladder: templates up to H5, then worked guidance (H6), full explanation (H7). */
function escalate(
  f: Flow,
  loop: ItemLoop,
  item: OpenItem,
  activity: ActivityType,
  rule: string,
  reasons: string[],
) {
  const cap = hintCap(activity);
  const stuck = loop.wrong_answers > FRUSTRATION_WRONG_ANSWERS;
  if (!stuck) {
    for (let level = loop.max_hint_level + 1; level <= Math.min(cap, 5); level++) {
      const hint = hintAt(f.ctx.lesson, item, level as HintLevel);
      if (hint) {
        f.run.say("HINT", hint.text, {
          hint_level: hint.level,
          hint_target: hint.target,
          rule_ids: [rule],
          reason_codes: reasons,
          source: hint.source,
        });
        return;
      }
    }
  }
  const steps = item.worked_solution ?? [];
  if (cap >= 6 && loop.max_hint_level < 6 && steps.length >= 2) {
    f.run.say("WORKED_GUIDANCE", PHRASES.worked(steps.slice(0, -1)), {
      hint_level: 6,
      hint_target: "STEP",
      rule_ids: ["R-FRUSTRATION"],
      reason_codes: [...reasons, stuck ? "STUCK" : "LADDER_EXHAUSTED"],
      source: "worked_solution",
    });
    return;
  }
  if (cap >= 7 && loop.max_hint_level < 7 && item.explanation) {
    loop.phase = "TEACH_BACK";
    f.run.say("FULL_EXPLANATION", PHRASES.fullExplanation(item.explanation), {
      hint_level: 7,
      hint_target: "CONCEPT",
      rule_ids: ["R-FULL"],
      reason_codes: reasons,
      source: "explanation",
    });
    return;
  }
  f.run.say("CLOSE_ITEM", PHRASES.moveOn, {
    rule_ids: ["MOCK-CAP-CLOSE"],
    reason_codes: [...reasons, "HINT_CAP_REACHED"],
  });
  closeItem(f, loop, "UNRESOLVED");
}
