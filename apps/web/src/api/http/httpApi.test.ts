import { describe, expect, it } from "vitest";

import { memoryStorage } from "../../test/memoryStorage";
import { ApiError, type SessionApi } from "../client";
import type { ChatTurn, SessionState, StreamEvent } from "../contract";
import { createHttpApi } from "./httpApi";

interface Call {
  method: string;
  path: string;
  headers: Record<string, string>;
  body: unknown;
}

type Route = (call: Call) => { status?: number; body?: unknown; text?: string };

/** A fetch that answers from a table of "METHOD /path" routes and records every call. */
function fakeServer(routes: Record<string, Route>) {
  const calls: Call[] = [];
  const fetchFn: typeof fetch = (input, init) => {
    const call: Call = {
      method: init?.method ?? "GET",
      path: typeof input === "string" ? input : input instanceof URL ? input.href : input.url,
      headers: { ...(init?.headers as Record<string, string>) },
      body: typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined,
    };
    calls.push(call);
    const route = routes[`${call.method} ${call.path}`] as Route | undefined;
    if (!route) return Promise.resolve(new Response("no route", { status: 404 }));
    const { status = 200, body, text } = route(call);
    return Promise.resolve(new Response(text ?? JSON.stringify(body), { status }));
  };
  return { fetchFn, calls };
}

function turn(sequence_no: number, actor: ChatTurn["actor"], text: string): ChatTurn {
  return {
    turn_id: `t${sequence_no}`,
    sequence_no,
    item_attempt_id: "a1",
    actor,
    text,
    occurred_at: "2026-10-01T03:00:00Z",
    move: actor === "tutor" ? "HINT" : null,
    hint_level: null,
  };
}

function stateOf(version: number, transcript: ChatTurn[]): SessionState {
  return {
    session_id: "s1",
    state_version: version,
    lifecycle_state: "ACTIVE",
    lesson: { lesson_id: "l1", title: "So sánh hai số thập phân" },
    student_display_name: "Minh",
    persona: { tutor_self: "cô", student_address: "con" },
    activity: { activity_id: "03-GUIDED_PRACTICE", type: "GUIDED_PRACTICE" },
    item: {
      item_attempt_id: "a1",
      item_id: "GP-01",
      stem: "0,25 … 0,3",
      answer_format: "compare",
      options: [],
      expecting: "ANSWER",
      position: 3,
    },
    pending_choice: null,
    allowed_commands: ["ANSWER", "HINT_REQUEST"],
    progress: { items_done: 2, items_total: 8 },
    transcript,
  };
}

const BEFORE = stateOf(4, [turn(1, "tutor", "0,25 … 0,3")]);
const AFTER = stateOf(5, [
  ...BEFORE.transcript,
  turn(2, "student", ">"),
  turn(3, "tutor", "Con so sánh hàng nào trước?"),
]);
const ANSWER = {
  item_attempt_id: "a1",
  kind: "ANSWER",
  content: { text: ">" },
  modality: "TEXT",
  expected_state_version: 4,
} as const;

function client(routes: Record<string, Route>, storage: Storage | null = null) {
  const server = fakeServer(routes);
  const api = createHttpApi({ fetch: server.fetchFn, storage, typingDelayMs: 0, newId: () => "browser-1" });
  return { api, calls: server.calls };
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

describe("createHttpApi", () => {
  it("creates a session with the demo identity of this browser and keeps that identity", async () => {
    const storage = memoryStorage();
    const { api, calls } = client({ "POST /v1/sessions": () => ({ status: 201, body: BEFORE }) }, storage);

    expect(api.engine).toBe("live");
    await expect(api.createDemoSession({ student_display_name: "Minh" })).resolves.toEqual({
      session_id: "s1",
    });
    expect(calls[0].headers["X-Demo-Student"]).toBe("browser-1");
    expect(calls[0].body).toEqual({ student_display_name: "Minh" });

    const again = createHttpApi({
      fetch: fakeServer({}).fetchFn,
      storage,
      newId: () => "another-id",
    });
    await again.getState("s1").catch(() => undefined);
    expect(storage.getItem("cavat.demo.student-id")).toBe("browser-1");
  });

  it("returns the ack, then streams only the new tutor turns and the new state", async () => {
    let reads = 0;
    const { api, calls } = client({
      "GET /v1/sessions/s1/state": () => ({ body: reads++ === 0 ? BEFORE : AFTER }),
      "POST /v1/sessions/s1/responses": () => ({
        body: { accepted: true, state_version: 5, tutor_turn_id: "t3" },
      }),
    });
    await api.getState("s1"); // the screen has shown turn 1
    const stream = untilState(api, "s1");

    const ack = await api.submitResponse("s1", ANSWER, "key-1");

    expect(ack).toEqual({ accepted: true, state_version: 5, tutor_turn_id: "t3" });
    const post = calls.find((c) => c.method === "POST");
    expect(post?.headers).toMatchObject({ "Idempotency-Key": "key-1", "X-Demo-Student": "browser-1" });
    expect(post?.body).toEqual(ANSWER);

    const events = await stream;
    const deltas = events.flatMap((e) => (e.event === "tutor.delta" ? [e.data] : []));
    expect(deltas.every((d) => d.turn_id === "t3")).toBe(true);
    expect(deltas.map((d) => d.delta).join("")).toBe("Con so sánh hàng nào trước?");
    expect(events.filter((e) => e.event === "tutor.final").map((e) => e.data)).toEqual([AFTER.transcript[2]]);
    expect(events.at(-1)).toEqual({ event: "state", data: AFTER });
  });

  it("turns the error body into an ApiError and anything else into a plain failure", async () => {
    const conflict = {
      error: { code: "STATE_VERSION_CONFLICT", message: "reload", details: { expected: 4, current: 5 } },
    };
    const { api } = client({
      "POST /v1/sessions/s1/responses": () => ({ status: 409, body: conflict }),
      "GET /v1/sessions/s1/state": () => ({ status: 502, text: "Bad Gateway" }),
    });

    const error: unknown = await api.submitResponse("s1", ANSWER, "key-1").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: "STATE_VERSION_CONFLICT", isStale: true });
    expect((error as ApiError).details).toEqual({ expected: 4, current: 5 });

    const down: unknown = await api.getState("s1").catch((e: unknown) => e);
    expect(down).toBeInstanceOf(Error);
    expect(down).not.toBeInstanceOf(ApiError);
  });

  it("rejects the command when the state cannot be read afterwards, and streams nothing", async () => {
    const { api } = client({
      "POST /v1/sessions/s1/hint-requests": () => ({
        body: { accepted: true, state_version: 5, tutor_turn_id: "t3" },
      }),
      "GET /v1/sessions/s1/state": () => ({ status: 500, text: "boom" }),
    });
    const events: StreamEvent[] = [];
    api.subscribe("s1", (event) => events.push(event));

    await expect(
      api.requestHint("s1", { item_attempt_id: "a1", expected_state_version: 4 }, "key-1"),
    ).rejects.toThrow("HTTP 500");
    expect(events).toEqual([]);
  });

  it("uses the teacher header, not the student identity, for the teacher's calls", async () => {
    const { api, calls } = client({
      "GET /v1/sessions": () => ({ body: [] }),
      "GET /v1/sessions/s%2F1/transcript": () => ({ body: { session: {}, segments: [] } }),
    });

    await expect(api.listSessions()).resolves.toEqual([]);
    await api.getTranscript("s/1"); // the id is escaped in the path
    for (const call of calls) {
      expect(call.headers["X-Demo-Teacher"]).toBeTruthy();
      expect(call.headers["X-Demo-Student"]).toBeUndefined();
    }
    expect(api.resetDemoData).toBeUndefined(); // demo data lives on the server, not in this browser
  });
});
