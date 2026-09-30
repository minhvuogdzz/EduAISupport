import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SessionApi } from "../../api/client";
import { memoryStorage } from "../../test/memoryStorage";
import { renderApp, testApi } from "../../test/renderApp";

async function openSession(api: SessionApi = testApi(), name = "An") {
  const { session_id } = await api.createDemoSession({ student_display_name: name });
  const rendered = renderApp(`/student/sessions/${session_id}`, api);
  await screen.findByRole("heading", { name: "Câu 1/8" });
  return { ...rendered, sessionId: session_id };
}

/** Waits until the tutor has finished answering. */
async function waitForTurn() {
  await waitFor(() => {
    expect(screen.queryByText("Cô đang trả lời…")).not.toBeInTheDocument();
    expect(screen.queryByTestId("typing")).not.toBeInTheDocument();
  });
}

/** Numbers are wrapped in their own spans, so match on the conversation's text content. */
async function expectInConversation(text: string) {
  await waitFor(() => expect(screen.getByRole("log")).toHaveTextContent(text));
}

async function answer(user: ReturnType<typeof renderApp>["user"], text: string) {
  await waitForTurn();
  await user.click(screen.getByRole("textbox"));
  await user.paste(text);
  await user.keyboard("{Enter}");
}

describe("student session screen", () => {
  it("joins the session and shows greeting, question, answer box and hint button", async () => {
    await openSession();
    expect(screen.getByRole("heading", { level: 1, name: "So sánh hai số thập phân" })).toBeInTheDocument();
    expect(screen.getByText("Khởi động")).toBeInTheDocument();
    await expectInConversation("Chào An!");
    expect(screen.getByLabelText("Câu trả lời của con")).toBeEnabled();
    expect(screen.getByRole("button", { name: /Xin gợi ý/ })).toBeEnabled();
    expect(screen.getByRole("progressbar", { name: "Tiến độ buổi học" })).toHaveAttribute(
      "aria-valuenow",
      "0",
    );
    // CC-01 is a choice item: its options are offered as quick answers.
    expect(screen.getByRole("button", { name: "hàng phần mười" })).toBeInTheDocument();
  });

  it("shows decimals the vi-VN way and marks the blank of a fill-in stem", async () => {
    const { user } = await openSession();
    await user.click(screen.getByRole("button", { name: "hàng phần mười" }));
    await user.click(screen.getByRole("button", { name: "Gửi" }));
    const card = await screen.findByRole("region", { name: "Câu 2/8" });
    expect(card).toHaveTextContent("Điền dấu >, < hoặc = vào chỗ chấm: 0,7 …chỗ trống 0,65");
    expect(within(card).getByText("0,65")).toHaveClass("whitespace-nowrap", "tabular-nums");
    // "0,7 … 0,65" is one unbreakable group: the number spans share a nowrap parent.
    const group = within(card).getByText("0,7").parentElement;
    expect(group).toHaveClass("whitespace-nowrap");
    expect(group).toContainElement(within(card).getByText("0,65"));
    expect(screen.getByText("Viết số thập phân bằng dấu phẩy, ví dụ 0,25.")).toBeInTheDocument();
  });

  it("answers with the sign buttons, gets a counter-example for DEC-M01, then moves on", async () => {
    const { user } = await openSession();
    await answer(user, "hàng phần mười");
    await screen.findByRole("heading", { name: "Câu 2/8" });
    await waitForTurn();

    await user.click(screen.getByRole("button", { name: "dấu bé hơn" })); // 0,7 < 0,65: DEC-M01
    expect(screen.getByLabelText("Câu trả lời của con")).toHaveValue("<");
    await user.click(screen.getByRole("button", { name: "Gửi" }));
    await expectInConversation("Nếu có 0,7 mét dây và 0,65 mét dây");
    expect(within(screen.getByRole("log")).getByText("Gợi ý mức 2")).toBeInTheDocument();

    await answer(user, "0,7 > 0,65");
    await screen.findByRole("heading", { name: "Câu 3/8" });
    expect(screen.getByRole("progressbar", { name: "Tiến độ buổi học" })).toHaveAttribute(
      "aria-valuenow",
      "2",
    );
    expect(screen.getByText("Luyện tập cùng cô")).toBeInTheDocument();
  });

  it("offers a micro choice on 'Xin gợi ý', then gives the chosen help", async () => {
    const { user } = await openSession();
    await user.click(screen.getByRole("button", { name: /Xin gợi ý/ }));
    const choices = await screen.findByRole("group", { name: "Con chọn một cách" });
    await expectInConversation("Con xin gợi ý.");
    await waitForTurn();
    expect(screen.getByRole("button", { name: /Xin gợi ý/ })).toBeDisabled(); // choose first

    await user.click(within(choices).getByRole("button", { name: "Gợi ý nhỏ" }));
    await expectInConversation("Chữ số 4 đứng ở bên trái hay bên phải dấu phẩy?");
    expect(within(screen.getByRole("log")).getByText("Gợi ý mức 1")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByRole("group", { name: "Con chọn một cách" })).not.toBeInTheDocument(),
    );
  });

  it("asks for an explanation after a correct answer on a verify item", async () => {
    const { user } = await openSession();
    await answer(user, "hàng phần mười");
    await answer(user, ">");
    await screen.findByRole("heading", { name: "Câu 3/8" });
    await answer(user, "0,25 < 0,3");
    expect(await screen.findByLabelText("Lời giải thích của con")).toBeInTheDocument();
    expect(screen.getByText("Cô muốn nghe con giải thích")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Xin gợi ý/ })).toBeDisabled();
  });

  it("re-reads the state and keeps the draft when another tab answered first (409)", async () => {
    const storage = memoryStorage();
    const { user, sessionId } = await openSession(testApi({ storage }));
    const otherTab = testApi({ storage });
    const state = await otherTab.getState(sessionId);
    await otherTab.submitResponse(
      sessionId,
      {
        item_attempt_id: state.item!.item_attempt_id,
        kind: "ANSWER",
        content: { text: "phần mười" },
        modality: "TEXT",
        expected_state_version: state.state_version,
      },
      "other-tab",
    );

    await user.type(screen.getByRole("textbox"), "phần trăm{Enter}");
    expect(
      await screen.findByText("Bài vừa được cập nhật. Con xem lại rồi gửi lại nhé."),
    ).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Câu 2/8" })).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toHaveValue("phần trăm");
    await user.click(screen.getByRole("button", { name: "Đã hiểu" }));
    expect(screen.queryByText(/Bài vừa được cập nhật/)).not.toBeInTheDocument();
  });

  it("tells the student when the session does not exist", async () => {
    renderApp("/student/sessions/nope");
    expect(await screen.findByText(/Không tìm thấy buổi học này/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Trang học sinh" })).toHaveAttribute("href", "/student");
  });

  it("shows the completion card at the end", { timeout: 20_000 }, async () => {
    const { user } = await openSession();
    const answers = [
      "hàng phần mười",
      ">",
      "<",
      "vì 2 < 3",
      "<",
      "Hoa",
      "vì 9,75 < 9,8",
      "sai",
      "vì 2 < 3",
      ">",
      "Minh",
    ];
    for (const text of answers) await answer(user, text);
    expect(await screen.findByText("Con đã hoàn thành buổi học!")).toBeInTheDocument();
    expect(screen.getByText("Con đã làm 8/8 câu.")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
