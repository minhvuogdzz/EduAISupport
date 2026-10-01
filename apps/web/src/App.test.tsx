import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { renderApp, testApi } from "./test/renderApp";

describe("App", () => {
  afterEach(() => localStorage.clear());

  it("goes from the home page to a new session through the student start page", async () => {
    const { user } = renderApp("/");
    expect(
      screen.getByText("Chế độ giả lập (mock): chưa nối máy chủ. Lời của cô là câu mẫu, chưa phải AI tutor."),
    ).toBeVisible();
    await user.click(screen.getByRole("link", { name: /Học sinh/ }));

    const start = screen.getByRole("button", { name: "Bắt đầu học" });
    expect(start).toBeDisabled();
    await user.type(screen.getByLabelText("Con tên là gì?"), "Bình");
    await user.click(start);

    expect(await screen.findByRole("heading", { name: "Câu 1/8" })).toBeInTheDocument();
    expect(screen.getByRole("log")).toHaveTextContent("Chào Bình!");
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

  it("shows a not-found page for unknown paths", () => {
    renderApp("/khong-co");
    expect(screen.getByRole("heading", { name: "Không tìm thấy trang này" })).toBeInTheDocument();
  });
});
