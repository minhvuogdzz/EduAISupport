import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderApp, testApi } from "../../test/renderApp";
import { ENGLISH_UNITS } from "./content";

describe("English preview", () => {
  it("lists every topic and marks English as the current subject", async () => {
    renderApp("/student/english");
    const subjects = await screen.findByRole("navigation", { name: "Chọn môn học" });
    expect(within(subjects).getByRole("link", { name: /Tiếng Anh/ })).toHaveAttribute("aria-current", "page");
    expect(within(subjects).getByRole("link", { name: /Toán/ })).not.toHaveAttribute("aria-current");
    for (const unit of ENGLISH_UNITS) {
      expect(screen.getByRole("link", { name: new RegExp(unit.title) })).toBeInTheDocument();
    }
  });

  it("answers any question only by saying the lesson is being prepared, without calling the API", async () => {
    const api = testApi();
    const createDemoSession = vi.spyOn(api, "createDemoSession");
    const { user } = renderApp(`/student/english/${ENGLISH_UNITS[0].id}`, api);
    const input = await screen.findByLabelText("Câu hỏi của con");
    expect(screen.queryByText("Cô đang chuẩn bị bài giảng")).not.toBeInTheDocument();

    await user.type(input, "Hello nghĩa là gì?{Enter}");

    expect(screen.getByRole("log")).toHaveTextContent("Hello nghĩa là gì?");
    expect(screen.getByRole("status")).toHaveTextContent("Cô đang chuẩn bị bài giảng");
    expect(input).toHaveValue("");
    expect(createDemoSession).not.toHaveBeenCalled();
  });

  it("does not send an empty question", async () => {
    const { user } = renderApp(`/student/english/${ENGLISH_UNITS[0].id}`);
    await user.type(await screen.findByLabelText("Câu hỏi của con"), "   {Enter}");
    expect(screen.queryByText("Cô đang chuẩn bị bài giảng")).not.toBeInTheDocument();
  });

  it("labels the parent's English levels as samples", async () => {
    renderApp("/parent/english");
    expect(await screen.findByRole("heading", { level: 1, name: "Tiếng Anh của con" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: /minh họa/ })).toBeInTheDocument();
    for (const unit of ENGLISH_UNITS) expect(screen.getByText(unit.title)).toBeInTheDocument();
  });

  it("shows the teacher the draft topics and a sample class under a tab of its own", async () => {
    renderApp("/teacher/english");
    expect(await screen.findByRole("link", { name: "Tiếng Anh" })).toHaveAttribute("aria-current", "page");
    expect(screen.getAllByText("Bản nháp, chưa duyệt")).toHaveLength(ENGLISH_UNITS.length);
    expect(screen.getByRole("heading", { level: 2, name: /minh họa/ })).toBeInTheDocument();
  });

  it("offers English from the parent's page", async () => {
    renderApp("/parent");
    const subjects = await screen.findByRole("navigation", { name: "Chọn môn học" });
    expect(within(subjects).getByRole("link", { name: /Tiếng Anh/ })).toHaveAttribute(
      "href",
      "/parent/english",
    );
  });

  it("says so when the topic does not exist", async () => {
    renderApp("/student/english/khong-co");
    expect(await screen.findByRole("alert")).toHaveTextContent("Chưa có chủ đề này");
  });
});
