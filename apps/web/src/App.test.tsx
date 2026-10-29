import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { renderApp, testApi } from "./test/renderApp";

describe("App", () => {
  afterEach(() => localStorage.clear());

  it("goes from the home page to a new session through the student start page", async () => {
    const { user } = renderApp("/");
    expect(
      screen.getByText(
        "Chế độ giả lập (mock): chưa nối máy chủ. Lời của cô là câu mẫu, chưa phải lời của Gia sư Buddy.",
      ),
    ).toBeVisible();
    const roles = screen.getByRole("navigation", { name: "Vai trò" });
    await user.click(within(roles).getByRole("button", { name: "Học sinh" }));

    // One student in the trial (ACC-2): no name to type, the demo student is An.
    expect(screen.queryByLabelText("Con tên là gì?")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Bắt đầu buổi mới/ }));

    expect(await screen.findByRole("heading", { name: "Câu 1/8" })).toBeInTheDocument();
    expect(screen.getByRole("log")).toHaveTextContent("Chào An!");
  });

  it("offers to resume the unfinished session of this device", async () => {
    const api = testApi();
    const { session_id } = await api.createDemoSession({ student_display_name: "Chi" });
    await api.join(session_id);
    localStorage.setItem("cavat.student.last-session", session_id);

    const { user } = renderApp("/student", api);
    expect(await screen.findByText(/còn dang dở/)).toHaveTextContent(
      "Buổi học của Chi còn dang dở (đã xong 0/8 câu).",
    );
    await user.click(screen.getByRole("link", { name: "Học tiếp" }));
    expect(await screen.findByRole("heading", { name: "Câu 1/8" })).toBeInTheDocument();
  });

  it("lists this student's sessions under Lịch sử học, each one to open again", async () => {
    const api = testApi();
    const first = await api.createDemoSession({ student_display_name: "Chi" });
    await api.join(first.session_id);
    await api.createDemoSession({ student_display_name: "Chi" });

    renderApp("/student", api);
    const history = await screen.findByRole("region", { name: "Lịch sử học" });
    const links = within(history).getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAccessibleName(/^Học tiếp buổi So sánh hai số thập phân lúc /);
    expect(within(history).getAllByText(/0\/8 câu/)).toHaveLength(2);
  });

  it("shows a not-found page for unknown paths", () => {
    renderApp("/khong-co");
    expect(screen.getByRole("heading", { name: "Không tìm thấy trang này" })).toBeInTheDocument();
  });
});
