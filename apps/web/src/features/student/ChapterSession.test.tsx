import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SessionApi } from "../../api/client";
import type { ResponseCommand, SessionState, StreamEvent } from "../../api/contract";
import { renderApp } from "../../test/renderApp";
import { checkState, THEORY_ASK, theoryState } from "../../test/teachingFixtures";

/** A live API that answers one reply: theory question -> concept-check item. */
function chapterApi() {
  let state: SessionState = theoryState();
  const sent: ResponseCommand[] = [];
  const listeners = new Set<(event: StreamEvent) => void>();
  const api: SessionApi = {
    engine: "live",
    createDemoSession: () => Promise.resolve({ session_id: state.session_id }),
    getState: () => Promise.resolve(state),
    join: () => Promise.resolve(state),
    submitResponse: (_id, command) => {
      sent.push(command);
      state = checkState(command.content.text);
      queueMicrotask(() => listeners.forEach((listener) => listener({ event: "state", data: state })));
      return Promise.resolve({ accepted: true, state_version: state.state_version, tutor_turn_id: null });
    },
    requestHint: () => Promise.reject(new Error("not used")),
    choose: () => Promise.reject(new Error("not used")),
    subscribe: (_id, onEvent) => {
      listeners.add(onEvent);
      return () => listeners.delete(onEvent);
    },
    listSessions: () => Promise.resolve([]),
    listMySessions: () => Promise.resolve([]),
    getTranscript: () => Promise.reject(new Error("not used")),
  };
  return { api, sent };
}

describe("chapter session screen (M1-7)", () => {
  it("teaches with a theory card, the step of the cycle and the node map", async () => {
    renderApp("/student/sessions/s-1", chapterApi().api);
    expect(await screen.findByRole("heading", { level: 1, name: "Số thập phân" })).toBeInTheDocument();
    expect(screen.getByText("Cô giảng bài")).toBeInTheDocument();
    expect(screen.getByRole("log")).toHaveTextContent("Sợi dây dài 2 m 7 dm");
    const prompt = screen.getByRole("region", { name: "Cô hỏi con" });
    expect(prompt).toHaveTextContent(THEORY_ASK);
    // One step bar for desktop (side column), one for tablets; CSS shows one of them.
    const [steps] = screen.getAllByRole("navigation", { name: "Các bước học bài Khái niệm số thập phân" });
    expect(within(steps).getByText("Giảng bài").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.queryByRole("button", { name: /Xin gợi ý/ })).not.toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Tiến độ chương" })).toHaveAttribute("aria-valuenow", "1");
    expect(screen.getAllByText("Khái niệm số thập phân: Đang học, Làm theo mẫu").length).toBeGreaterThan(0);
  });

  it("sends the reply with the tutor's input id, then shows the concept check", async () => {
    const { api, sent } = chapterApi();
    const { user } = renderApp("/student/sessions/s-1", api);
    await user.click(await screen.findByPlaceholderText("Con trả lời cô ở đây…"));
    await user.paste("Phần nguyên là 2");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toMatchObject({
      item_attempt_id: "in-1",
      kind: "MESSAGE",
      content: { text: "Phần nguyên là 2" },
      expected_state_version: 3,
    });
    expect(await screen.findByRole("region", { name: "Kiểm tra hiểu" })).toHaveTextContent(
      "Số 12,45 có phần nguyên là bao nhiêu?",
    );
    expect(screen.getByRole("button", { name: /Xin gợi ý/ })).toBeInTheDocument();
  });
});
