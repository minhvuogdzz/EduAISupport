import { describe, expect, it } from "vitest";

import { memoryStorage } from "../../test/memoryStorage";
import { ApiError, type SessionApi } from "../client";
import type { SessionState, StreamEvent } from "../contract";
import { createMockApi, type MockApiOptions } from "./mockApi";

const fast = (options: MockApiOptions = {}) =>
  createMockApi({ latencyMs: 0, typingDelayMs: 0, seed: false, storage: null, ...options });

async function startedSession(api: SessionApi, name = "An") {
  const { session_id } = await api.createDemoSession({ student_display_name: name });
  const state = await api.join(session_id);
  return { id: session_id, state };
}

/** Collects stream events until the next `state` event. */
function untilState(api: SessionApi, sessionId: string): Promise<StreamEvent[]> {
  return new Promise((resolve) => {
    const events: StreamEvent[] = [];
    const unsubscribe = api.subscribe(sessionId, (event) => {
      events.push(event);
      if (event.event === "state") {
        unsubscribe();
        resolve(events);
      }
    });
  });
}

function answerCommand(state: SessionState, text: string) {
  return {
    item_attempt_id: state.item!.item_attempt_id,
    kind: "ANSWER" as const,
    content: { text },
    modality: "TEXT" as const,
    expected_state_version: state.state_version,
  };
}

async function expectApiError(promise: Promise<unknown>, status: number, code: string) {
  const error: unknown = await promise.then(
    () => null,
    (e: unknown) => e,
  );
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ status, code });
  return error as ApiError;
}

describe("mock SessionApi", () => {
  it("creates a READY session and joins it idempotently", async () => {
    const api = fast();
    const { session_id } = await api.createDemoSession({ student_display_name: "  An " });
    expect((await api.getState(session_id)).lifecycle_state).toBe("READY");

    const joined = await api.join(session_id);
    expect(joined).toMatchObject({
      lifecycle_state: "ACTIVE",
      student_display_name: "An",
      activity: { activity_id: "A3", type: "CONCEPT_CHECK" },
      item: { item_id: "CC-01", answer_format: "choice", expecting: "ANSWER", position: 1 },
      allowed_commands: ["ANSWER", "HINT_REQUEST"],
      progress: { items_done: 0, items_total: 8 },
    });
    expect(joined.item?.options.map((o) => o.text)).toEqual([
      "hàng phần mười",
      "hàng phần trăm",
      "hàng đơn vị",
    ]);
    expect(joined.item?.options[0]).not.toHaveProperty("correct");

    const rejoined = await api.join(session_id); // resume, no second greeting
    expect(rejoined.transcript).toEqual(joined.transcript);
    expect(rejoined.state_version).toBe(joined.state_version);
  });

  it("rejects an empty or too long name", async () => {
    const api = fast();
    await expectApiError(api.createDemoSession({ student_display_name: "  " }), 400, "VALIDATION_ERROR");
    await expectApiError(
      api.createDemoSession({ student_display_name: "x".repeat(31) }),
      400,
      "VALIDATION_ERROR",
    );
  });

  it("acks a response, then streams tutor.delta …, tutor.final and the new state", async () => {
    const api = fast();
    const { id, state } = await startedSession(api);
    const streamed = untilState(api, id);
    const ack = await api.submitResponse(id, answerCommand(state, "phần mười"), "key-1");
    expect(ack).toMatchObject({ accepted: true, state_version: state.state_version + 1 });

    const events = await streamed;
    const finals = events.flatMap((e) => (e.event === "tutor.final" ? [e.data] : []));
    expect(finals.map((t) => t.move)).toEqual(["CONFIRM_ADVANCE", "PRESENT"]);
    expect(ack.tutor_turn_id).toBe(finals[0].turn_id);
    const deltas = events.flatMap((e) =>
      e.event === "tutor.delta" && e.data.turn_id === finals[0].turn_id ? [e] : [],
    );
    expect(deltas.map((e) => e.data.delta).join("")).toBe(finals[0].text);

    const last = events.at(-1);
    expect(last?.event).toBe("state");
    const next = (last as Extract<StreamEvent, { event: "state" }>).data;
    expect(next.state_version).toBe(ack.state_version);
    expect(next.item?.item_id).toBe("CC-02");
    expect(next.transcript.map((t) => t.actor).slice(-3)).toEqual(["student", "tutor", "tutor"]);
  });

  it("replays the first result for a repeated Idempotency-Key, without new events", async () => {
    const api = fast();
    const { id, state } = await startedSession(api);
    const command = answerCommand(state, "phần mười");
    const first = await api.submitResponse(id, command, "same-key");
    const second = await api.submitResponse(id, command, "same-key");
    expect(second).toEqual(first);
    const after = await api.getState(id);
    expect(after.state_version).toBe(first.state_version);
    expect(after.transcript.filter((t) => t.actor === "student")).toHaveLength(1);
  });

  it("rejects a stale state_version with 409 and tells the current version", async () => {
    const api = fast();
    const { id, state } = await startedSession(api);
    await api.submitResponse(id, answerCommand(state, "phần trăm"), "k1"); // same item, version + 1
    const error = await expectApiError(
      api.submitResponse(id, answerCommand(state, "phần mười"), "k2"),
      409,
      "STATE_VERSION_CONFLICT",
    );
    expect(error.isStale).toBe(true);
    expect(error.details).toEqual({ state_version: state.state_version + 1 });
  });

  it("rejects an answer for an item that is no longer current (STALE_ITEM)", async () => {
    const api = fast();
    const { id, state } = await startedSession(api);
    await api.submitResponse(id, answerCommand(state, "phần mười"), "k1"); // CC-01 done
    const current = await api.getState(id);
    const stale = { ...answerCommand(current, "<"), item_attempt_id: state.item!.item_attempt_id };
    await expectApiError(api.submitResponse(id, stale, "k2"), 409, "STALE_ITEM");
  });

  it("enforces allowed commands on the server, not only in the UI (design rule 4)", async () => {
    const api = fast();
    const { id, state } = await startedSession(api);
    const choice = { choice_id: "SMALL", expected_state_version: state.state_version };
    await expectApiError(api.choose(id, choice, "k1"), 409, "COMMAND_NOT_ALLOWED_IN_ACTIVITY");
    await expectApiError(api.choose(id, { ...choice, choice_id: "ANSWER" }, "k2"), 400, "VALIDATION_ERROR");

    await api.requestHint(
      id,
      { item_attempt_id: state.item!.item_attempt_id, expected_state_version: 2 },
      "k3",
    );
    const offered = await api.getState(id);
    expect(offered.pending_choice?.map((c) => c.choice_id)).toEqual(["SMALL", "EXAMPLE"]);
    expect(offered.allowed_commands).toEqual(["ANSWER", "CHOICE"]);
    const hint = {
      item_attempt_id: offered.item!.item_attempt_id,
      expected_state_version: offered.state_version,
    };
    await expectApiError(api.requestHint(id, hint, "k4"), 409, "COMMAND_NOT_ALLOWED_IN_ACTIVITY");
  });

  it("returns 404 for an unknown session", async () => {
    await expectApiError(fast().getState("nope"), 404, "NOT_FOUND");
  });

  it("shares sessions between instances on the same storage (student tab → teacher tab)", async () => {
    const storage = memoryStorage();
    const student = fast({ storage });
    const teacher = fast({ storage });
    const { id } = await startedSession(student, "Bình");
    const sessions = await teacher.listSessions();
    expect(sessions.map((s) => s.student_display_name)).toEqual(["Bình"]);
    expect((await teacher.getTranscript(id)).session.lifecycle_state).toBe("ACTIVE");

    await teacher.resetDemoData?.();
    expect(await student.listSessions()).toEqual([]);
  });
});

describe("mock SessionApi: demo data", () => {
  it("seeds two sessions, newest first", async () => {
    const sessions = await fast({ seed: true }).listSessions();
    expect(sessions.map((s) => [s.student_display_name, s.lifecycle_state, s.progress.items_done])).toEqual([
      ["Lan", "ACTIVE", 1],
      ["Minh", "COMPLETED", 8],
    ]);
    expect(sessions[1].misconception_ids).toEqual(["DEC-M01"]);
    expect(sessions.every((s) => s.engine === "mock")).toBe(true);
  });

  it("is deterministic across browsers", async () => {
    const [a, b] = [fast({ seed: true }), fast({ seed: true })];
    const [idA] = (await a.listSessions()).map((s) => s.session_id);
    expect(await a.getTranscript(idA)).toEqual(await b.getTranscript(idA));
  });

  it("builds the teacher transcript: session lines and item blocks in timeline order", async () => {
    const api = fast({ seed: true });
    const minh = (await api.listSessions()).find((s) => s.student_display_name === "Minh")!;
    const { segments } = await api.getTranscript(minh.session_id);

    expect(segments.map((s) => (s.kind === "item" ? s.item_id : "session"))).toEqual([
      "session",
      "CC-01",
      "CC-02",
      "session",
      "GP-01",
      "GP-02",
      "GP-08",
      "GP-09",
      "session",
      "EX-01",
      "EX-03",
      "session",
    ]);

    const gp01 = segments.find((s) => s.kind === "item" && s.item_id === "GP-01");
    expect(gp01).toMatchObject({
      resolution: "SUPPORTED",
      max_hint_level: 2,
      activity_type: "GUIDED_PRACTICE",
    });
    const turns = gp01?.kind === "item" ? gp01.turns : [];
    expect(turns[1]).toMatchObject({
      actor: "student",
      text: "0,25 > 0,3",
      student: {
        outcome: "WRONG",
        normalized_answer: "0,25 > 0,3",
        misconception: { id: "DEC-M01", name: "Dài hơn thì lớn hơn", confidence: 0.9 },
      },
    });
    expect(turns[2]).toMatchObject({
      actor: "tutor",
      tutor: { move: "COGNITIVE_CONFLICT", hint_level: 2, hint_target: "CONCEPT", rule_ids: ["R-MISC-HIGH"] },
    });

    const exit = segments.find((s) => s.kind === "item" && s.item_id === "EX-01");
    expect(exit).toMatchObject({ resolution: null });
  });
});
