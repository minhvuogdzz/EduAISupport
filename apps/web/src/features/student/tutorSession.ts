/**
 * Client-side view of one tutor session: server snapshots merged with the SSE stream.
 *
 * The server owns the state (PART 31, failure handling): the screen only shows what a snapshot or the
 * stream confirmed, plus the student's own line marked "đang gửi" until the server has it. Input stays
 * locked from the moment a command is sent until a snapshot at least as new as its ack arrives.
 */
import type { ChatTurn, SessionState, StreamEvent } from "../../api/contract";

export interface TutorView {
  status: "loading" | "ready" | "not_found" | "not_owner" | "error";
  state: SessionState | null;
  /** Turns confirmed by a snapshot, in sequence order (kept across items, even if a snapshot trims). */
  turns: ChatTurn[];
  /** The student's line of the command in flight. */
  outgoing: string | null;
  /** tutor.final turns received since the last snapshot. */
  live: ChatTurn[];
  /** The tutor turn being streamed (tutor.delta). */
  typing: { turn_id: string; text: string } | null;
  /** Version of the last ack; the screen waits for a snapshot this new before accepting input. */
  awaitingVersion: number | null;
  sending: boolean;
  notice: string | null;
}

export type TutorAction =
  | { type: "loaded"; state: SessionState }
  | { type: "load_failed"; notFound: boolean; notOwner?: boolean }
  | { type: "sending"; line: string }
  | { type: "acked"; version: number }
  | { type: "rejected"; notice: string }
  | { type: "stream"; event: StreamEvent }
  | { type: "dismiss_notice" };

export const initialTutorView: TutorView = {
  status: "loading",
  state: null,
  turns: [],
  outgoing: null,
  live: [],
  typing: null,
  awaitingVersion: null,
  sending: false,
  notice: null,
};

function hasTurn(view: TutorView, turnId: string): boolean {
  return view.turns.some((t) => t.turn_id === turnId) || view.live.some((t) => t.turn_id === turnId);
}

function applySnapshot(view: TutorView, state: SessionState): TutorView {
  if (view.state && state.state_version < view.state.state_version) return view; // older than what we show
  const byId = new Map(view.turns.map((t) => [t.turn_id, t]));
  for (const turn of state.transcript) byId.set(turn.turn_id, turn);
  const turns = [...byId.values()].sort((a, b) => a.sequence_no - b.sequence_no);
  const confirmed = new Set(turns.map((t) => t.turn_id));
  const caughtUp = view.awaitingVersion === null || state.state_version >= view.awaitingVersion;
  return {
    ...view,
    state,
    turns,
    live: view.live.filter((t) => !confirmed.has(t.turn_id)),
    typing: view.typing && !confirmed.has(view.typing.turn_id) ? view.typing : null,
    awaitingVersion: caughtUp ? null : view.awaitingVersion,
    outgoing: caughtUp && !view.sending ? null : view.outgoing,
  };
}

function applyStream(view: TutorView, event: StreamEvent): TutorView {
  switch (event.event) {
    case "tutor.delta": {
      const { turn_id, delta } = event.data;
      if (hasTurn(view, turn_id)) return view;
      const text = view.typing?.turn_id === turn_id ? view.typing.text + delta : delta;
      return { ...view, typing: { turn_id, text } };
    }
    case "tutor.final": {
      const turn = event.data;
      const typing = view.typing?.turn_id === turn.turn_id ? null : view.typing;
      if (hasTurn(view, turn.turn_id)) return { ...view, typing };
      return { ...view, live: [...view.live, turn], typing };
    }
    case "state":
      return applySnapshot(view, event.data);
  }
}

export function tutorReducer(view: TutorView, action: TutorAction): TutorView {
  switch (action.type) {
    case "loaded":
      return { ...applySnapshot(view, action.state), status: "ready" };
    case "load_failed":
      return { ...view, status: action.notFound ? "not_found" : action.notOwner ? "not_owner" : "error" };
    case "sending":
      return { ...view, sending: true, outgoing: action.line, notice: null };
    case "acked": {
      const caughtUp = view.state !== null && view.state.state_version >= action.version;
      return {
        ...view,
        sending: false,
        awaitingVersion: caughtUp ? null : action.version,
        outgoing: caughtUp ? null : view.outgoing,
      };
    }
    case "rejected":
      return { ...view, sending: false, outgoing: null, notice: action.notice };
    case "stream":
      return applyStream(view, action.event);
    case "dismiss_notice":
      return { ...view, notice: null };
  }
}

/** True while the student must wait: a command is in flight or the tutor is still answering. */
export function isBusy(view: TutorView): boolean {
  return view.sending || view.awaitingVersion !== null || view.typing !== null;
}

/** A turn as shown: the student's line of the command in flight is marked pending. */
export type DisplayTurn = ChatTurn & { pending?: true };

/**
 * Confirmed turns, then the student's pending line, then tutor turns streamed after it. Confirmed
 * turns are passed through as the same objects, so memoized bubbles skip re-rendering while the
 * tutor's next turn streams in word by word.
 */
export function displayTurns(view: TutorView): DisplayTurn[] {
  if (view.outgoing === null) return [...view.turns, ...view.live];
  const pending: DisplayTurn = {
    turn_id: "outgoing",
    sequence_no: Number.MAX_SAFE_INTEGER,
    item_attempt_id: view.state?.item?.item_attempt_id ?? null,
    actor: "student",
    text: view.outgoing,
    occurred_at: "",
    move: null,
    hint_level: null,
    pending: true,
  };
  return [...view.turns, pending, ...view.live];
}
