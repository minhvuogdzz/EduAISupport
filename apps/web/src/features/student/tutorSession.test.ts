import { describe, expect, it } from "vitest";

import type { ChatTurn, SessionState } from "../../api/contract";
import {
  displayTurns,
  initialTutorView,
  isBusy,
  tutorReducer,
  type TutorAction,
  type TutorView,
} from "./tutorSession";

const turn = (sequence_no: number, actor: ChatTurn["actor"], text: string): ChatTurn => ({
  turn_id: `t${sequence_no}`,
  sequence_no,
  item_attempt_id: "attempt-1",
  actor,
  text,
  occurred_at: "2026-09-30T01:00:00Z",
  move: actor === "tutor" ? "PRESENT" : null,
  hint_level: null,
});

const state = (state_version: number, transcript: ChatTurn[]): SessionState => ({
  session_id: "s1",
  state_version,
  lifecycle_state: "ACTIVE",
  lesson: { lesson_id: "l1", title: "So sánh hai số thập phân" },
  student_display_name: "An",
  persona: { tutor_self: "cô", student_address: "con" },
  activity: { activity_id: "A5", type: "GUIDED_PRACTICE" },
  item: null,
  pending_choice: null,
  allowed_commands: ["ANSWER", "HINT_REQUEST"],
  progress: { items_done: 0, items_total: 8 },
  transcript,
});

const run = (...actions: TutorAction[]): TutorView => actions.reduce(tutorReducer, initialTutorView);
const texts = (view: TutorView) =>
  displayTurns(view).map((t) => `${t.actor}:${t.text}${t.pending ? " (…)" : ""}`);

const question = turn(1, "tutor", "0,25 … 0,3?");
const answer = turn(2, "student", "0,25 > 0,3");
const reply = turn(3, "tutor", "Nếu có 0,25 mét dây…");

describe("tutorReducer", () => {
  it("shows the student's line as pending, then the streamed reply after it, then the snapshot", () => {
    const loaded: TutorAction = { type: "loaded", state: state(2, [question]) };
    let view = run(loaded, { type: "sending", line: "0,25 > 0,3" });
    expect(texts(view)).toEqual(["tutor:0,25 … 0,3?", "student:0,25 > 0,3 (…)"]);
    expect(isBusy(view)).toBe(true);

    view = [
      { type: "acked", version: 3 },
      { type: "stream", event: { event: "tutor.delta", data: { turn_id: "t3", delta: "Nếu " } } },
      { type: "stream", event: { event: "tutor.delta", data: { turn_id: "t3", delta: "có" } } },
    ].reduce<TutorView>((v, a) => tutorReducer(v, a as TutorAction), view);
    expect(view.typing).toEqual({ turn_id: "t3", text: "Nếu có" });
    expect(isBusy(view)).toBe(true);

    view = tutorReducer(view, { type: "stream", event: { event: "tutor.final", data: reply } });
    expect(view.typing).toBeNull();
    expect(texts(view)).toEqual([
      "tutor:0,25 … 0,3?",
      "student:0,25 > 0,3 (…)",
      "tutor:Nếu có 0,25 mét dây…",
    ]);
    expect(isBusy(view)).toBe(true); // still waiting for the state of version 3

    view = tutorReducer(view, {
      type: "stream",
      event: { event: "state", data: state(3, [question, answer, reply]) },
    });
    expect(texts(view)).toEqual(["tutor:0,25 … 0,3?", "student:0,25 > 0,3", "tutor:Nếu có 0,25 mét dây…"]);
    expect(isBusy(view)).toBe(false);
  });

  it("unlocks when the snapshot arrived before the ack", () => {
    const view = run(
      { type: "loaded", state: state(2, [question]) },
      { type: "sending", line: "0,25 > 0,3" },
      { type: "stream", event: { event: "state", data: state(3, [question, answer, reply]) } },
      { type: "acked", version: 3 },
    );
    expect(view.outgoing).toBeNull();
    expect(isBusy(view)).toBe(false);
    expect(texts(view)).toHaveLength(3);
  });

  it("ignores a snapshot older than the one on screen", () => {
    const view = run(
      { type: "loaded", state: state(3, [question, answer, reply]) },
      { type: "stream", event: { event: "state", data: state(2, [question]) } },
    );
    expect(view.state?.state_version).toBe(3);
    expect(view.turns).toHaveLength(3);
  });

  it("keeps earlier turns when a snapshot only carries the current item (PART 29)", () => {
    const next = { ...turn(4, "tutor", "Câu mới"), item_attempt_id: "attempt-2" };
    const view = run(
      { type: "loaded", state: state(3, [question, answer, reply]) },
      { type: "stream", event: { event: "state", data: state(4, [next]) } },
    );
    expect(view.turns.map((t) => t.turn_id)).toEqual(["t1", "t2", "t3", "t4"]);
  });

  it("drops deltas and finals of turns it already has", () => {
    const view = run(
      { type: "loaded", state: state(3, [question, answer, reply]) },
      { type: "stream", event: { event: "tutor.delta", data: { turn_id: "t3", delta: "again" } } },
      { type: "stream", event: { event: "tutor.final", data: reply } },
    );
    expect(view.typing).toBeNull();
    expect(view.live).toEqual([]);
  });

  it("retires a server-removed wait notice from snapshots and streamed turns", () => {
    const wait = turn(2, "tutor", "Con chờ cô một chút nhé.");
    const guidance = turn(4, "tutor", "Con viết 7/10 thành số thập phân nào?");
    for (const initial of [
      run({ type: "loaded", state: state(2, [question, wait]) }),
      run(
        { type: "loaded", state: state(1, [question]) },
        { type: "stream", event: { event: "tutor.final", data: wait } },
      ),
    ]) {
      const view = tutorReducer(initial, {
        type: "stream",
        event: { event: "state", data: state(3, [question, guidance]) },
      });
      expect(displayTurns(view)).toEqual([question, guidance]);
    }
  });

  it("clears the pending line and shows a notice when a command is rejected", () => {
    const view = run(
      { type: "loaded", state: state(2, [question]) },
      { type: "sending", line: "<" },
      { type: "rejected", notice: "Bài vừa được cập nhật." },
    );
    expect(view.outgoing).toBeNull();
    expect(view.notice).toBe("Bài vừa được cập nhật.");
    expect(isBusy(view)).toBe(false);
    expect(tutorReducer(view, { type: "dismiss_notice" }).notice).toBeNull();
  });

  it("reports load failures", () => {
    expect(run({ type: "load_failed", notFound: true }).status).toBe("not_found");
    expect(run({ type: "load_failed", notFound: false }).status).toBe("error");
  });
});
