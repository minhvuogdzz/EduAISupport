/**
 * Demo sessions for the teacher screen, produced by driving the mock engine with scripted answers.
 * Deterministic (fixed clock and ids), so every browser shows the same data.
 */
import {
  allowedCommands,
  applyCommand,
  newSession,
  startSession,
  type EngineContext,
  type MockCommand,
  type MockSession,
} from "./engine";
import type { LessonPackage } from "./lessonTypes";

const answer = (text: string): MockCommand => ({ type: "ANSWER", kind: "ANSWER", text, modality: "TEXT" });
const explain = (text: string): MockCommand => ({
  type: "ANSWER",
  kind: "EXPLANATION",
  text,
  modality: "TEXT",
});
const askHint: MockCommand = { type: "HINT_REQUEST" };
const choose = (choice_id: string): MockCommand => ({ type: "CHOICE", choice_id });

interface Script {
  name: string;
  joinedAt: string;
  steps: MockCommand[];
}

const SCRIPTS: Script[] = [
  {
    // Finishes the session: a probe, DEC-M01 twice, a micro choice, three verifications.
    name: "Minh",
    joinedAt: "2026-09-29T01:00:00Z",
    steps: [
      answer("phần trăm"), // CC-01: wrong (DEC-M03, low confidence) → PROBE
      answer("hàng phần mười"), // CC-01: correct
      answer(">"), // CC-02: correct
      answer("0,25 > 0,3"), // GP-01: DEC-M01 → cognitive conflict
      answer("0,25 < 0,3"), // GP-01: correct → verify
      explain("Vì ở hàng phần mười, 0,25 có chữ số 2 còn 0,3 có chữ số 3, mà 2 bé hơn 3."),
      askHint, // GP-02: micro choice
      choose("SMALL"), // → H1
      answer("<"), // GP-02: correct
      answer("Hoa ạ"), // GP-08: correct → verify
      explain("Vì Hoa chạy hết 9,75 giây, ít hơn 9,8 giây của Lan."),
      answer("đúng"), // GP-09: DEC-M01 → concept hint
      answer("sai"), // GP-09: correct → verify
      explain("Bạn An so sánh 25 với 3 như số tự nhiên, nhưng phải so sánh từng hàng."),
      answer(">"), // EX-01: recorded, not graded in the mock
      answer("Minh"), // EX-03: recorded → summary
    ],
  },
  {
    // Still learning: stuck on CC-02 with DEC-M01.
    name: "Lan",
    joinedAt: "2026-09-30T01:30:00Z",
    steps: [answer("phần mười"), answer("<")],
  },
];

export function seedSessions(lesson: LessonPackage): Record<string, MockSession> {
  const sessions: Record<string, MockSession> = {};
  SCRIPTS.forEach((script, index) => {
    const prefix = `demo-${index + 1}`;
    let clock = Date.parse(script.joinedAt) - 60_000;
    let ids = 0;
    const ctx: EngineContext = {
      lesson,
      now: () => new Date(clock),
      newId: () => `${prefix}-${String(++ids).padStart(4, "0")}`,
    };
    const session = newSession(ctx, script.name);
    clock += 60_000;
    startSession(ctx, session);
    script.steps.forEach((step, n) => {
      clock += 25_000;
      if (!allowedCommands(session).includes(step.type)) {
        throw new Error(`seed ${script.name}, step ${n + 1}: ${step.type} is not allowed here`);
      }
      applyCommand(ctx, session, step, `${prefix}-key-${n + 1}`);
    });
    sessions[session.session_id] = session;
  });
  return sessions;
}
