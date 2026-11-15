import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SessionApi } from "../../api/client";
import { renderApp, testApi } from "../../test/renderApp";

const UNIT = "eng-g5-u11-family-time";

/** No page of English may present it as skills or as one score (ADR-060 §2). */
function expectNoSkillsOrScore() {
  const text = document.body.textContent ?? "";
  expect(text).not.toMatch(/Bốn kỹ năng|Nghe, nói, đọc, viết|English\s*=/);
  expect(text).not.toContain("khung Toán");
}

describe("English, Unit 11 (ENG-7a)", () => {
  it("shows the student the unit, the six-step loop and the unit's knowledge map", async () => {
    renderApp("/student/english");
    const subjects = await screen.findByRole("navigation", { name: "Chọn môn học" });
    expect(within(subjects).getByRole("link", { name: /Tiếng Anh/ })).toHaveAttribute("aria-current", "page");
    const units = await screen.findByRole("navigation", { name: "Chọn unit" });
    expect(within(units).getByRole("button", { name: /Family time/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    const loop = screen.getByRole("list", { name: /Các bước ôn/ });
    expect(within(loop).getAllByRole("listitem")).toHaveLength(6);
    expect(within(loop).getByText("Luyện tập").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getAllByText("Mục tiêu tiếp theo").length).toBeGreaterThan(0);

    for (const name of [
      "Cụm từ hoạt động kỳ nghỉ",
      "Dạng quá khứ của động từ",
      "Trọng âm trong câu hỏi Wh-",
    ]) {
      expect(screen.getAllByText(name).length).toBeGreaterThan(0);
    }
    expect(screen.getByRole("heading", { name: "Con đã nói được" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Mình ôn thêm nhé" })).toBeInTheDocument();
    expectNoSkillsOrScore();
  });

  it("runs a session on the shared session screen: theory, reply, question card, hint", async () => {
    const { user } = renderApp("/student/english");
    await user.click(await screen.findByRole("button", { name: /Bắt đầu buổi mới/ }));

    expect(await screen.findByText(/bạn Mary hỏi Mai/)).toBeInTheDocument();
    const box = await screen.findByRole("textbox");
    await user.type(box, "Yes, I did.{Enter}");

    expect(await screen.findByText(/Bạn hỏi bằng did nên con đáp bằng did/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "walk" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Xin gợi ý/ }));
    expect(await screen.findByText(/Did đã cho biết đây là chuyện đã qua chưa/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Tiến độ unit" })).toBeInTheDocument();
  });

  it("gives the teacher the class on the unit, with the voice share and the ASR_LOW warning", async () => {
    renderApp("/teacher/english");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Lớp học · Tiếng Anh · Unit 11: Family time" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tiếng Anh" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("navigation", { name: "Unit" })).toBeInTheDocument();
    expect(screen.getByText(/% câu trả lời bằng giọng nói/)).toBeInTheDocument();
    expect(screen.getByText(/Nhiều lượt nói nghe chưa rõ/)).toBeInTheDocument();
    expect(screen.getByText(/Sau We dùng động từ nguyên mẫu/, { selector: "span" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "An" })).toHaveAttribute(
      "href",
      `/teacher/english/students/demo-an?chapter=${UNIT}`,
    );
    expectNoSkillsOrScore();
  });

  it("reports one student with English dimensions, the four groups and the spoken turns", async () => {
    const api = testApi();
    const audio = vi.spyOn(api.englishDemo!, "getTurnAudio");
    const { user } = renderApp(`/teacher/english/students/demo-an?chapter=${UNIT}`, api);
    expect(await screen.findByRole("heading", { level: 1, name: "Học sinh An" })).toBeInTheDocument();

    expect(screen.getByRole("img", { name: /Hiểu vì sao/ })).toBeInTheDocument(); // the radar
    for (const label of ["Tự làm", "Nhờ gợi ý", "Sau khi cô đọc mẫu", "Chưa xong"]) {
      expect(within(screen.getByRole("list", { name: "Chú giải" })).getByText(label)).toBeInTheDocument();
    }
    const voice = screen.getByRole("region", { name: "Lượt nói của con" });
    expect(within(voice).getByText("Yes I do")).toBeInTheDocument(); // verbatim, never corrected
    expect(within(voice).getAllByText(/Nghe chưa rõ \(không trừ điểm\)/).length).toBeGreaterThan(0);
    expect(within(voice).getAllByText(/Nghe rõ/).length).toBeGreaterThan(0);
    expect(within(voice).getAllByText(/Nghe tạm/).length).toBeGreaterThan(0);
    expect(within(voice).getByText("Nghe tiếng Việt")).toBeInTheDocument();
    expect(within(voice).getByText("Đã được giáo viên điều chỉnh")).toBeInTheDocument();
    expect(screen.getAllByText(/Nhiều lượt nói nghe chưa rõ/).length).toBeGreaterThan(0);

    await user.click(within(voice).getByRole("button", { name: /Nghe lại lượt nói: Yes I do/ }));
    await waitFor(() => expect(audio).toHaveBeenCalledWith("an-v7"));
    expectNoSkillsOrScore();
  });

  it("tells the parent in words only: no score, no transcript, no audio", async () => {
    renderApp("/parent/english/A1B2C3");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Tình hình học của An" }),
    ).toBeInTheDocument();
    const status = screen.getByRole("region", { name: "Tình hình Tiếng Anh của con" });
    for (const title of ["Đã nắm chắc", "Cần luyện thêm", "Mục tiêu tiếp theo"]) {
      expect(within(status).getByRole("heading", { name: title })).toBeInTheDocument();
    }
    expect(screen.getByText(/Con hay đáp “Yes, I do.” khi bạn hỏi/)).toBeInTheDocument();
    expect(screen.getByText("“Did you take photos?”")).toBeInTheDocument(); // a sentence to try at home
    const text = document.body.textContent ?? "";
    expect(text).not.toContain("Yes I do");
    expect(text).not.toContain("Nghe lại");
    expect(text).not.toMatch(/\bM \d/);
    expectNoSkillsOrScore();
  });

  it("opens the child's English from the math page's link and from the code form", async () => {
    renderApp("/parent/english?code=A1B2C3");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Tình hình học của An" }),
    ).toBeInTheDocument();
  });

  it("keeps the math pages as they were", async () => {
    renderApp("/student");
    expect(await screen.findByRole("button", { name: /Bắt đầu buổi mới/ })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Chọn unit" })).not.toBeInTheDocument();
    expect(screen.queryByText("Vòng ôn bài 6 bước")).not.toBeInTheDocument();
    const subjects = screen.getByRole("navigation", { name: "Chọn môn học" });
    expect(within(subjects).getByRole("link", { name: /Toán/ })).toHaveAttribute("aria-current", "page");
  });
});

/**
 * The real API (ENG-7b): no `englishDemo`. The server is played by the demo's answers, so what is checked is
 * the path: which endpoint, with which unit and subject; the client never sends a subject for a view.
 */
function realApi() {
  const demo = testApi().englishDemo!;
  const base = testApi();
  const api: SessionApi = {
    ...base,
    englishDemo: undefined,
    getTaughtChapters: vi.fn((subject?: string) =>
      Promise.resolve(
        subject === "english"
          ? [{ chapter_id: UNIT, title: "Unit 11: Family time", subject: "english" as const }]
          : [{ chapter_id: "math-g5-decimals", title: "Số thập phân" }],
      ),
    ),
    getClassOverview: vi.fn((chapter?: string) => demo.getClassOverview!(chapter)),
    getStudentReport: vi.fn((id: string, chapter?: string) => demo.getStudentReport!(id, chapter)),
    getChildOverview: vi.fn((code: string, chapter?: string) => demo.getChildOverview!(code, chapter)),
    getMyOverview: vi.fn((chapter?: string) => demo.getMyOverview!(chapter)),
    getTurnAudio: vi.fn(() => Promise.resolve(new Blob(["opus"], { type: "audio/webm" }))),
    getTranscript: vi.fn(() => Promise.reject(new Error("not in this test"))),
  };
  return api;
}

describe("English on the real API (ENG-7b)", () => {
  it("asks the server for the teacher's units and the unit's class, never a preview label", async () => {
    const api = realApi();
    renderApp("/teacher/english", api);
    expect(
      await screen.findByRole("heading", { level: 1, name: "Lớp học · Tiếng Anh · Unit 11: Family time" }),
    ).toBeInTheDocument();
    await waitFor(() => expect(api.getTaughtChapters).toHaveBeenCalledWith("english"));
    expect(api.getClassOverview).toHaveBeenCalledWith(UNIT);
    expect(screen.queryByText("Bản xem trước")).not.toBeInTheDocument();
  });

  it("plays a spoken turn through the teacher-only endpoint", async () => {
    const api = realApi();
    const { user } = renderApp(`/teacher/english/students/demo-an?chapter=${UNIT}`, api);
    expect(await screen.findByRole("heading", { level: 1, name: "Học sinh An" })).toBeInTheDocument();
    expect(api.getStudentReport).toHaveBeenCalledWith("demo-an", UNIT);
    const voice = screen.getByRole("region", { name: "Lượt nói của con" });
    await user.click(within(voice).getByRole("button", { name: /Nghe lại lượt nói: Yes I do/ }));
    await waitFor(() => expect(api.getTurnAudio).toHaveBeenCalledWith("an-v7"));
  });

  it("gives the parent the unit's words, with no recording endpoint called", async () => {
    const api = realApi();
    renderApp("/parent/english/A1B2C3", api);
    expect(
      await screen.findByRole("heading", { level: 1, name: "Tình hình học của An" }),
    ).toBeInTheDocument();
    expect(api.getChildOverview).toHaveBeenCalledWith("A1B2C3", UNIT);
    expect(api.getTurnAudio).not.toHaveBeenCalled();
    expect(document.body.textContent ?? "").not.toContain("Nghe lại");
  });
});
