import { useEffect, useReducer, useState } from "react";

import { useApi } from "../../api/apiContext";
import { ApiError } from "../../api/client";
import type { CommandAck, MicroChoice, Modality, ResponseKind, SessionState } from "../../api/contract";
import { newId } from "../../lib/ids";
import { displayTurns, initialTutorView, isBusy, tutorReducer } from "./tutorSession";

const HINT_LINE = "Con xin gợi ý.";
const NOTICE_STALE = "Bài vừa được cập nhật. Con xem lại rồi gửi lại nhé.";
const NOTICE_FAILED = "Chưa gửi được. Con thử lại nhé.";

/** One tutor session: snapshot + stream from the API, and the three student commands. */
export function useTutorSession(sessionId: string) {
  const api = useApi();
  const [view, dispatch] = useReducer(tutorReducer, initialTutorView);
  const [recoveryFailures, setRecoveryFailures] = useState(0);

  useEffect(() => {
    let active = true;
    const unsubscribe = api.subscribe(sessionId, (event) => dispatch({ type: "stream", event }));
    void (async () => {
      try {
        let state = await api.getState(sessionId);
        // Joining starts a READY session and resumes one the student left (PART 24.4).
        if (["READY", "ACTIVE", "EXITED", "INTERRUPTED"].includes(state.lifecycle_state))
          state = await api.join(sessionId);
        if (active) dispatch({ type: "loaded", state });
      } catch (error) {
        if (active)
          dispatch({
            type: "load_failed",
            notFound: error instanceof ApiError && error.code === "NOT_FOUND",
            notOwner: error instanceof ApiError && error.code === "NOT_SESSION_OWNER",
          });
      }
    })();
    return () => {
      active = false;
      unsubscribe();
    };
  }, [api, sessionId]);

  const commandBusy = isBusy(view);
  const state = view.state;
  const pending = state?.tutor_recovery;
  const retrying = pending?.status === "retrying" && recoveryFailures < 3 && Boolean(api.recover);
  const busy = commandBusy || retrying;

  useEffect(() => {
    if (!state || !retrying || commandBusy || !api.recover) return;
    let active = true;
    const key = `recover-${sessionId}-${state.state_version}`;
    const timer = setTimeout(
      () => {
        void (async () => {
          try {
            const ack = await api.recover!(sessionId, state.state_version, key);
            if (!active) return;
            dispatch({ type: "acked", version: ack.state_version });
            // Also reload when a second tab already recovered the command or the stream was missed.
            const fresh = await api.getState(sessionId);
            if (active) {
              setRecoveryFailures(0);
              dispatch({ type: "loaded", state: fresh });
            }
          } catch {
            if (!active) return;
            setRecoveryFailures((n) => n + 1);
            try {
              const fresh = await api.getState(sessionId);
              if (active) dispatch({ type: "loaded", state: fresh });
            } catch {
              // Bounded retries also apply to a disconnected browser.
            }
          }
        })();
      },
      Math.max(pending?.retry_after_ms ?? 2000, recoveryFailures ? 5000 : 0),
    );
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [api, sessionId, state, pending, retrying, commandBusy, recoveryFailures]);

  useEffect(() => {
    if (recoveryFailures >= 3)
      dispatch({
        type: "rejected",
        notice: "Chưa kết nối lại được. Bài vẫn được giữ, con quay lại buổi học sau nhé.",
      });
  }, [recoveryFailures]);

  /** Sends one command with a fresh Idempotency-Key; on 409 re-reads the state (PART 24.2). */
  async function send(line: string, command: (state: SessionState, key: string) => Promise<CommandAck>) {
    const state = view.state;
    if (!state || busy) return false;
    setRecoveryFailures(0);
    dispatch({ type: "sending", line });
    try {
      const ack = await command(state, newId());
      dispatch({ type: "acked", version: ack.state_version });
      return true;
    } catch (error) {
      const stale = error instanceof ApiError && error.isStale;
      dispatch({ type: "rejected", notice: stale ? NOTICE_STALE : NOTICE_FAILED });
      if (stale) {
        try {
          dispatch({ type: "loaded", state: await api.getState(sessionId) });
        } catch {
          // keep the notice; the next stream event or reload brings the state back
        }
      }
      return false;
    }
  }

  function submitAnswer(text: string, modality: Modality = "TEXT") {
    return send(text, (state, key) =>
      api.submitResponse(
        sessionId,
        {
          item_attempt_id: state.item?.item_attempt_id ?? state.teaching?.input_id ?? "",
          kind: responseKind(state),
          content: { text },
          modality,
          expected_state_version: state.state_version,
        },
        key,
      ),
    );
  }

  function requestHint() {
    return send(HINT_LINE, (state, key) =>
      api.requestHint(
        sessionId,
        { item_attempt_id: state.item?.item_attempt_id ?? "", expected_state_version: state.state_version },
        key,
      ),
    );
  }

  function choose(choice: MicroChoice) {
    return send(choice.label, (state, key) =>
      api.choose(
        sessionId,
        { choice_id: choice.choice_id, expected_state_version: state.state_version },
        key,
      ),
    );
  }

  return {
    view,
    busy,
    turns: displayTurns(view),
    submitAnswer,
    requestHint,
    choose,
    dismissNotice: () => dispatch({ type: "dismiss_notice" }),
  };
}

/** What the student's words are: an answer, an explanation ("vì sao", retell) or a reply to a question. */
function responseKind(state: SessionState): ResponseKind {
  if (state.item) return state.item.expecting === "EXPLANATION" ? "EXPLANATION" : "ANSWER";
  if (state.teaching?.awaiting === "RETELL") return "EXPLANATION";
  if (state.teaching?.awaiting === "THEORY_REPLY") return "MESSAGE";
  return "ANSWER";
}
