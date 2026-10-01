import { describe, expect, it } from "vitest";

import { HINT_MOVES, type HintLevel, type Move } from "../contract";
import {
  allowedCommands,
  applyCommand,
  newSession,
  startSession,
  type EngineContext,
  type EventPayloads,
  type MockCommand,
  type MockSession,
} from "./engine";
import { LESSON } from "./lesson";

const answer = (text: string): MockCommand => ({ type: "ANSWER", kind: "ANSWER", text, modality: "TEXT" });
const explain = (text: string): MockCommand => ({
  type: "ANSWER",
  kind: "EXPLANATION",
  text,
  modality: "TEXT",
});
const askHint: MockCommand = { type: "HINT_REQUEST" };
const choose = (choice_id: string): MockCommand => ({ type: "CHOICE", choice_id });

/** A correct answer for every item of the mock plan. */
const CORRECT: Record<string, string> = {
  "CC-01": "hàng phần mười",
  "CC-02": ">",
  "GP-01": "<",
  "GP-02": "<",
  "GP-08": "Hoa",
  "GP-09": "sai",
  "EX-01": ">",
  "EX-03": "Minh",
};

type TutorMessage = EventPayloads["TUTOR_MESSAGE_SENT"];

function harness() {
  let clock = Date.parse("2026-09-30T01:00:00Z");
  let ids = 0;
  const ctx: EngineContext = {
    lesson: LESSON,
    now: () => new Date((clock += 1000)),
    newId: () => `id-${++ids}`,
  };
  const session: MockSession = newSession(ctx, "An");
  startSession(ctx, session);

  function tutorMessages(from = 0): TutorMessage[] {
    return session.events
      .slice(from)
      .flatMap((e) => (e.event_type === "TUTOR_MESSAGE_SENT" ? [e.payload] : []));
  }

  /** Sends a command (asserting it is allowed) and returns the tutor messages it produced. */
  function send(command: MockCommand): TutorMessage[] {
    expect(allowedCommands(session)).toContain(command.type);
    const before = session.events.length;
    applyCommand(ctx, session, command, null);
    return tutorMessages(before);
  }

  /** Answers correctly (explaining when asked) until `itemId` is the current item. */
  function skipTo(itemId: string) {
    while (session.item && session.item.item_id !== itemId) {
      const expectingExplanation = session.item.phase === "VERIFYING" || session.item.phase === "TEACH_BACK";
      send(
        expectingExplanation ? explain("Vì con so sánh từng hàng.") : answer(CORRECT[session.item.item_id]),
      );
    }
    expect(session.item?.item_id).toBe(itemId);
  }

  function resolutions() {
    return session.events.flatMap((e) =>
      e.event_type === "ITEM_RESOLVED" ? [[e.payload.item_id, e.payload.resolution] as const] : [],
    );
  }

  return { session, send, skipTo, tutorMessages, resolutions };
}

const moves = (messages: TutorMessage[]): (Move | null)[] => messages.map((m) => m.move);

describe("mock engine: session flow", () => {
  it("starts with a greeting, the concept-check intro and the first question", () => {
    const { session, tutorMessages } = harness();
    expect(session.lifecycle_state).toBe("ACTIVE");
    expect(session.state_version).toBe(2);
    expect(moves(tutorMessages())).toEqual([null, null, "PRESENT"]);
    expect(tutorMessages()[0].text).toContain("An");
    expect(session.item).toMatchObject({ item_id: "CC-01", position: 1, phase: "AWAITING" });
    expect(allowedCommands(session)).toEqual(["ANSWER", "HINT_REQUEST"]);
  });

  it("confirms a correct answer and presents the next item", () => {
    const { session, send, resolutions } = harness();
    expect(moves(send(answer("hàng phần mười")))).toEqual(["CONFIRM_ADVANCE", "PRESENT"]);
    expect(resolutions()).toEqual([["CC-01", "INDEPENDENT"]]);
    expect(session.item).toMatchObject({ item_id: "CC-02", position: 2 });
  });

  it("runs the whole plan to the summary", () => {
    const { session, skipTo, send, tutorMessages } = harness();
    skipTo("EX-03");
    send(answer("Minh"));
    expect(session.lifecycle_state).toBe("COMPLETED");
    expect(session.item).toBeNull();
    expect(allowedCommands(session)).toEqual([]);
    expect(tutorMessages().at(-1)?.text).toContain("8 câu");
    expect(session.events.at(-1)?.event_type).toBe("SESSION_COMPLETED");
  });

  it("numbers events 1..n and stamps every event with school_id (design rule 5)", () => {
    const { session, skipTo } = harness();
    skipTo("GP-02");
    session.events.forEach((event, i) => {
      expect(event.sequence_no).toBe(i + 1);
      expect(event.school_id).toBe("demo-school");
    });
  });
});

describe("mock engine: rules", () => {
  it("DEC-M01 → cognitive conflict with the lesson's counter-example, then verify, then close", () => {
    const { session, send, skipTo, resolutions } = harness();
    skipTo("GP-01");
    const [conflict] = send(answer("0,25 > 0,3"));
    expect(conflict).toMatchObject({
      move: "COGNITIVE_CONFLICT",
      hint_level: 2,
      hint_target: "CONCEPT",
      rule_ids: ["R-MISC-HIGH"],
    });
    expect(conflict.text).toContain("0,25 mét dây và 0,3 mét dây");

    const [verify] = send(answer("0,25 < 0,3"));
    expect(verify).toMatchObject({ move: "VERIFY", rule_ids: ["R-CORRECT", "R-VERIFY"] });
    expect(session.item?.phase).toBe("VERIFYING");
    expect(allowedCommands(session)).toEqual(["ANSWER"]);

    expect(moves(send(explain("Vì hàng phần mười 2 < 3.")))[0]).toBe("CLOSE_ITEM");
    expect(resolutions().at(-1)).toEqual(["GP-01", "SUPPORTED"]);
  });

  it("probes a first wrong answer without a clear misconception, then escalates one level at a time", () => {
    const { send, skipTo } = harness();
    skipTo("GP-08");
    const [probe] = send(answer("Lan")); // DEC-M01 via the option, but confidence 0.6 < 0.7
    expect(probe).toMatchObject({ move: "PROBE", rule_ids: ["R-FIRST-WRONG"] });
    expect(send(answer("Lan"))[0]).toMatchObject({ move: "HINT", hint_level: 1, rule_ids: ["R-ESCALATE"] });
    expect(send(answer("Lan"))[0]).toMatchObject({ move: "HINT", hint_level: 2 });
  });

  it("asks which help the student wants, then gives a small hint or a similar example", () => {
    const { session, send, skipTo } = harness();
    skipTo("GP-02");
    const [offer] = send(askHint);
    expect(offer).toMatchObject({ move: "OFFER_CHOICE", rule_ids: ["R-HELP-REQUEST"] });
    expect(session.item?.phase).toBe("AWAITING_CHOICE");
    expect(allowedCommands(session)).toEqual(["ANSWER", "CHOICE"]);

    const [example] = send(choose("EXAMPLE"));
    expect(example).toMatchObject({ move: "HINT", hint_level: 3, hint_target: "STRATEGY" });
    expect(example.text).toContain("0,7 < 0,72"); // worked solution of the twin item GP-02b
    expect(session.item?.phase).toBe("AWAITING");

    expect(send(askHint)[0]).toMatchObject({ move: "HINT", hint_level: 4 }); // second request: no menu
  });

  it("treats 'con không biết' like a hint request and 'abc' as unreadable", () => {
    const { send, skipTo } = harness();
    skipTo("GP-01");
    expect(send(answer("abc"))[0]).toMatchObject({ move: "REDIRECT", rule_ids: ["R-REDIRECT"] });
    expect(send(answer("con không biết"))[0]).toMatchObject({ move: "OFFER_CHOICE" });
  });

  it("walks a stuck student to worked guidance (H6), full explanation (H7), teach-back, WORKED", () => {
    const { session, send, skipTo, resolutions } = harness();
    skipTo("GP-02");
    const replies = [1, 2, 3, 4, 5].map(() => send(answer("0,4 > 0,45"))[0]);
    expect(replies.map((m) => [m.move, m.hint_level])).toEqual([
      ["COGNITIVE_CONFLICT", 2],
      ["HINT", 3],
      ["HINT", 4],
      ["WORKED_GUIDANCE", 6],
      ["FULL_EXPLANATION", 7],
    ]);
    expect(replies[3].text).not.toContain("0,4 < 0,45"); // the last step stays for the student
    expect(session.item?.phase).toBe("TEACH_BACK");
    send(explain("Viết 0,4 thành 0,40 rồi so sánh hàng phần trăm."));
    expect(resolutions().at(-1)).toEqual(["GP-02", "WORKED"]);
  });

  it("caps hints at H3 in CONCEPT_CHECK and closes the item when the ladder ends", () => {
    const { send, skipTo, resolutions } = harness();
    skipTo("CC-02");
    const replies = [1, 2, 3].map(() => send(answer("<"))[0]);
    expect(replies.map((m) => [m.move, m.hint_level])).toEqual([
      ["COGNITIVE_CONFLICT", 2],
      ["HINT", 3],
      ["CLOSE_ITEM", null],
    ]);
    expect(resolutions().at(-1)).toEqual(["CC-02", "UNRESOLVED"]);
  });

  it("records EXIT answers without grading and allows one H1 hint (R-ASSESS-CAP)", () => {
    const { send, skipTo, resolutions } = harness();
    skipTo("EX-01");
    expect(send(askHint)[0]).toMatchObject({ move: "HINT", hint_level: 1, rule_ids: ["R-ASSESS-CAP"] });
    expect(send(askHint)[0]).toMatchObject({ move: "NUDGE", hint_level: null, rule_ids: ["R-ASSESS-CAP"] });
    expect(send(answer("<"))[0]).toMatchObject({ move: "CLOSE_ITEM", rule_ids: ["MOCK-EXIT-RECORD"] });
    expect(resolutions().at(-1)).toEqual(["EX-01", null]);
  });
});

describe("mock engine: invariants", () => {
  const CAPS: [string, HintLevel][] = [
    ["CC-01", 3],
    ["GP-09", 7],
    ["EX-03", 1],
  ];

  it.each(CAPS)("never goes above the activity cap (%s ≤ H%i)", (itemId, cap) => {
    const { session, send, skipTo } = harness();
    skipTo(itemId);
    for (let i = 0; i < 12 && session.item?.item_id === itemId; i++) {
      const phase = session.item.phase;
      if (phase === "AWAITING_CHOICE") send(choose("SMALL"));
      else if (phase === "VERIFYING" || phase === "TEACH_BACK") send(explain("..."));
      else send(i % 3 === 0 ? askHint : answer("xyz"));
    }
    const levels = session.events.flatMap((e) =>
      e.event_type === "HINT_DELIVERED" && e.item_attempt_id ? [e.payload.hint_level] : [],
    );
    expect(Math.max(0, ...levels)).toBeLessThanOrEqual(cap);
  });

  it("every question-type move asks exactly one question, in at most 60 words", () => {
    const { send, skipTo, tutorMessages } = harness();
    skipTo("GP-01");
    send(answer("0,25 > 0,3"));
    send(askHint);
    send(choose("EXAMPLE"));
    skipTo("GP-02");
    for (let i = 0; i < 5; i++) send(answer("0,4 > 0,45"));
    const asking = new Set<Move>(["PROBE", "HINT", "COGNITIVE_CONFLICT", "OFFER_CHOICE", "VERIFY"]);
    for (const message of tutorMessages()) {
      expect(message.text.split(/\s+/).length, message.text).toBeLessThanOrEqual(60);
      if (message.move && (asking.has(message.move) || HINT_MOVES.includes(message.move))) {
        expect(message.text.match(/\?/g)?.length, message.text).toBe(1);
      }
    }
  });

  it("does not state the answer before FULL_EXPLANATION", () => {
    const { session, send, skipTo } = harness();
    skipTo("GP-01");
    const start = session.events.length;
    for (let i = 0; i < 4; i++) send(answer("0,25 > 0,3"));
    const said = session.events
      .slice(start)
      .flatMap((e) => (e.event_type === "TUTOR_MESSAGE_SENT" ? [e.payload] : []))
      .filter((m) => m.move !== "FULL_EXPLANATION");
    for (const message of said) expect(message.text).not.toContain("0,25 < 0,3");
  });
});
