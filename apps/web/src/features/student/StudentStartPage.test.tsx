import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, type SessionApi } from "../../api/client";
import type { ChapterRef, StudentOverview } from "../../api/contract";
import { renderApp, testApi } from "../../test/renderApp";

const DECIMALS: ChapterRef = { chapter_id: "math-g5-decimals", title: "Số thập phân" };
const AREA: ChapterRef = {
  chapter_id: "math-g5-area-triangle-trapezoid",
  title: "Diện tích hình tam giác, hình thang",
};

function overviewOf(chapter: ChapterRef, chapters: ChapterRef[] = [DECIMALS, AREA]): StudentOverview {
  return {
    student_display_name: "An",
    parent_code: "4ACA86",
    chapter,
    chapters,
    nodes: [
      {
        node_id: "N1",
        name: chapter === AREA ? "Đáy và đường cao" : "Phân số thập phân",
        layer: "BASIC",
        status: "CURRENT",
        level: 1,
        quality: "WITH_SUPPORT",
        order: 1,
        passed: false,
      },
    ],
    relations: [],
    passed: chapter === AREA ? 0 : 1,
    total: 2,
    sessions: { total: 1, completed: 0, unfinished: 1, minutes: 0 },
    study_days: [],
    streak: 0,
    this_week: { study_days: 0, passed: 0 },
    going_well: [],
    to_practise: [],
    current_session_id: null,
    last_session_at: null,
  };
}

/** The mock API with the overview of the real one: it answers for the chapter it is asked for. */
function studentApi(chapters: ChapterRef[] = [DECIMALS, AREA]) {
  const base = testApi();
  const getMyOverview = vi.fn((chapter?: string) =>
    chapter !== undefined && !chapters.some((c) => c.chapter_id === chapter)
      ? Promise.reject(new ApiError(404, "NOT_FOUND", "no such chapter"))
      : Promise.resolve(overviewOf(chapters.find((c) => c.chapter_id === chapter) ?? chapters[0], chapters)),
  );
  const createDemoSession = vi.fn((input: Parameters<SessionApi["createDemoSession"]>[0]) =>
    base.createDemoSession(input),
  );
  const api: SessionApi = { ...base, getMyOverview, createDemoSession };
  return { api, getMyOverview, createDemoSession };
}

describe("student home with several chapters (REFORM 4.4)", () => {
  afterEach(() => localStorage.clear());

  it("offers every chapter the tutor teaches, the first one picked", async () => {
    const { api, getMyOverview } = studentApi();
    renderApp("/student", api);
    const picker = await screen.findByRole("navigation", { name: "Chọn chương" });
    const [first, second] = within(picker).getAllByRole("button");
    expect(first).toHaveTextContent("Số thập phân");
    expect(first).toHaveAttribute("aria-pressed", "true");
    expect(second).toHaveTextContent("Diện tích hình tam giác, hình thang");
    expect(second).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("Chương Số thập phân: con đã qua 1/2 bài.")).toBeInTheDocument();
    expect(getMyOverview).toHaveBeenCalledWith(undefined); // the server's first chapter
    // a touch target of at least 44 px
    expect(second).toHaveClass("min-h-11");
  });

  it("shows the progress of the chapter picked, and keeps the pick in the link", async () => {
    const { api, getMyOverview } = studentApi();
    const { user } = renderApp("/student", api);
    await user.click(await screen.findByRole("button", { name: AREA.title }));

    expect(
      await screen.findByText("Chương Diện tích hình tam giác, hình thang: con đã qua 0/2 bài."),
    ).toBeVisible();
    expect(getMyOverview).toHaveBeenLastCalledWith(AREA.chapter_id);
    expect(screen.getByRole("button", { name: AREA.title })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: DECIMALS.title })).toHaveAttribute("aria-pressed", "false");
    expect(await screen.findByRole("region", { name: `Bản đồ chương ${AREA.title}` })).toBeInTheDocument();
  });

  it("starts the new session on the chapter picked", async () => {
    const { api, createDemoSession } = studentApi();
    const { user } = renderApp("/student", api);
    await user.click(await screen.findByRole("button", { name: AREA.title }));
    await screen.findByText(/Chương Diện tích hình tam giác, hình thang: con đã qua/);
    await user.click(screen.getByRole("button", { name: /Bắt đầu buổi mới/ }));

    await waitFor(() => expect(createDemoSession).toHaveBeenCalledTimes(1));
    // the client names the chapter; it never names a model or an activity
    expect(createDemoSession).toHaveBeenCalledWith({
      student_display_name: "An",
      chapter_id: AREA.chapter_id,
    });
  });

  it("opens on the chapter named in the link, and starts on it", async () => {
    const { api, getMyOverview, createDemoSession } = studentApi();
    const { user } = renderApp(`/student?chapter=${AREA.chapter_id}`, api);
    expect(await screen.findByText(/Chương Diện tích hình tam giác, hình thang: con đã qua/)).toBeVisible();
    expect(getMyOverview).toHaveBeenCalledWith(AREA.chapter_id);
    await user.click(screen.getByRole("button", { name: /Bắt đầu buổi mới/ }));
    await waitFor(() =>
      expect(createDemoSession).toHaveBeenCalledWith({
        student_display_name: "An",
        chapter_id: AREA.chapter_id,
      }),
    );
  });

  it("offers no choice when the tutor teaches one chapter only", async () => {
    const { api, createDemoSession } = studentApi([DECIMALS]);
    const { user } = renderApp("/student", api);
    expect(await screen.findByText("Chương Số thập phân: con đã qua 1/2 bài.")).toBeVisible();
    expect(screen.queryByRole("navigation", { name: "Chọn chương" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Bắt đầu buổi mới/ }));
    await waitFor(() =>
      expect(createDemoSession).toHaveBeenCalledWith({
        student_display_name: "An",
        chapter_id: DECIMALS.chapter_id,
      }),
    );
  });

  it("says so when the link names a chapter that does not exist", async () => {
    const { api } = studentApi();
    renderApp("/student?chapter=nope", api);
    expect(await screen.findByRole("alert")).toHaveTextContent("Chưa có chương này.");
    expect(screen.getByRole("link", { name: "Về chương đầu" })).toHaveAttribute("href", "/student");
  });

  it("names the chapter of the unfinished session when there are several", async () => {
    const { api } = studentApi();
    const { session_id } = await api.createDemoSession({ student_display_name: "An" });
    await api.join(session_id);
    localStorage.setItem("cavat.student.last-session", session_id);

    renderApp("/student", api);
    const resume = (await screen.findByText(/còn dang dở/)).closest("div")!;
    expect(resume).toHaveTextContent("So sánh hai số thập phân"); // the title of that session's lesson
  });
});
