import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type SessionApi } from "../../api/client";
import type { AuthUser, ParentChildView, StudentOverview } from "../../api/contract";
import { renderApp, testApi } from "../../test/renderApp";

const DECIMALS = { chapter_id: "math-g5-decimals", title: "Số thập phân" };
const AREA = { chapter_id: "math-g5-area-triangle-trapezoid", title: "Diện tích hình tam giác, hình thang" };

const OVERVIEW: StudentOverview = {
  student_display_name: "An",
  parent_code: "4ACA86",
  chapter: DECIMALS,
  chapters: [DECIMALS, AREA],
  nodes: [
    {
      node_id: "FRAC",
      name: "Phân số thập phân",
      layer: "BASIC",
      status: "PASSED",
      level: 3,
      quality: "INDEPENDENT",
      order: 1,
      passed: true,
    },
    {
      node_id: "CONCEPT",
      name: "Khái niệm số thập phân",
      layer: "BASIC",
      status: "CURRENT",
      level: 1,
      quality: "WITH_SUPPORT",
      order: 2,
      passed: false,
    },
    {
      node_id: "PLACE",
      name: "Giá trị theo hàng",
      layer: "BASIC",
      status: "LOCKED",
      level: null,
      quality: "NOT_STARTED",
      order: 3,
      passed: false,
    },
  ],
  relations: [
    { source: "FRAC", target: "CONCEPT", type: "PREREQUISITE" },
    { source: "CONCEPT", target: "PLACE", type: "PREREQUISITE" },
  ],
  passed: 1,
  total: 3,
  sessions: { total: 2, completed: 1, unfinished: 1, minutes: 0 },
  study_days: ["2026-10-05", "2026-10-06"],
  streak: 2,
  this_week: { study_days: 2, passed: 1 },
  going_well: [{ node_id: "FRAC", name: "Phân số thập phân", quality: "INDEPENDENT" }],
  to_practise: [
    {
      node_id: "CONCEPT",
      name: "Khái niệm số thập phân",
      quality: "WITH_SUPPORT",
      reason: "Còn hay nhầm: đọc phần thập phân như số tự nhiên",
    },
  ],
  current_session_id: "s-2",
  last_session_at: "2026-10-06T08:30:00Z",
};

const CHILD: ParentChildView = {
  ...OVERVIEW,
  trend: Array.from({ length: 28 }, (_, i) => {
    const date = new Date(Date.UTC(2026, 8, 9 + i)).toISOString().slice(0, 10);
    return { date, studied: i >= 26, passed: i === 27 ? 1 : 0, started: i >= 26 ? 1 : 0 };
  }),
  home_tips: [
    {
      node_id: "CONCEPT",
      name: "Khái niệm số thập phân",
      tip: "Cùng con đọc giá tiền ở siêu thị và chỉ ra phần nguyên, phần thập phân.",
    },
  ],
  session_list: [
    {
      session_id: "s-2",
      started_at: "2026-10-06T08:30:00Z",
      minutes: 0,
      lifecycle_state: "ACTIVE",
      passed_names: [],
    },
    {
      session_id: "s-1",
      started_at: "2026-10-05T08:30:00Z",
      minutes: 12,
      lifecycle_state: "COMPLETED",
      passed_names: ["Phân số thập phân"],
    },
  ],
};

function progressApi(overrides: Partial<SessionApi> = {}): SessionApi {
  return {
    ...testApi(),
    getMyOverview: () => Promise.resolve(OVERVIEW),
    getChildOverview: (code) =>
      code === CHILD.parent_code
        ? Promise.resolve(CHILD)
        : Promise.reject(new ApiError(404, "NOT_FOUND", "unknown code")),
    ...overrides,
  };
}

describe("parent pages (PART 27.1)", () => {
  it("opens the child's progress from the code, in upper case", async () => {
    const getChildOverview = vi.fn(progressApi().getChildOverview);
    const { user } = renderApp("/parent", progressApi({ getChildOverview }));
    await user.type(screen.getByRole("textbox", { name: "Mã học sinh của con" }), "4aca86");
    await user.click(screen.getByRole("button", { name: "Xem tình hình học" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: "Tình hình học của An" }),
    ).toBeInTheDocument();
    expect(getChildOverview).toHaveBeenCalledWith("4ACA86", undefined); // no chapter: the server's first
  });

  it("says how well the child understands each topic in words, never as a score", async () => {
    renderApp("/parent/4ACA86", progressApi());
    const understanding = await screen.findByRole("region", { name: "Con hiểu bài thế nào" });
    const rows = within(understanding).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Phân số thập phân");
    expect(rows[0]).toHaveTextContent("Tự làm được");
    expect(rows[1]).toHaveTextContent("Làm được khi có hỗ trợ");
    expect(rows[2]).toHaveTextContent("Chưa học");
    // No mastery number, no percentage, no transcript for parents.
    expect(understanding).not.toHaveTextContent(/%|điểm M|\bM\s*=/);
    expect(screen.queryByText(/Hội thoại/)).not.toBeInTheDocument();

    expect(screen.getByText("Bài đã vững").parentElement).toHaveTextContent("1/3");
    expect(screen.getByText("Thời gian học").parentElement).toHaveTextContent("dưới 1 phút");
    expect(screen.getByRole("region", { name: "Con cần luyện thêm" })).toHaveTextContent(
      "Còn hay nhầm: đọc phần thập phân như số tự nhiên",
    );
    expect(screen.getByRole("region", { name: "Gợi ý cho bố mẹ" })).toHaveTextContent("giá tiền ở siêu thị");
    expect(
      screen.getByRole("img", { name: "Số bài con đã qua theo từng ngày trong 4 tuần" }),
    ).toBeInTheDocument();
    const sessions = within(screen.getByRole("region", { name: "Các buổi học" })).getAllByRole("row");
    expect(sessions).toHaveLength(3);
    expect(sessions[2]).toHaveTextContent("12 phút");
    expect(sessions[2]).toHaveTextContent("Phân số thập phân");
  });

  it("lets the parent pick the chapter, and keeps it in the link (REFORM 4.4)", async () => {
    const getChildOverview = vi.fn((_code: string, chapter?: string) =>
      Promise.resolve({
        ...CHILD,
        chapter: chapter === AREA.chapter_id ? AREA : DECIMALS,
        passed: chapter === AREA.chapter_id ? 0 : 1,
      }),
    );
    const { user } = renderApp("/parent/4ACA86", progressApi({ getChildOverview }));
    const picker = await screen.findByRole("navigation", { name: "Chọn chương" });
    const [first, second] = within(picker).getAllByRole("button");
    expect(first).toHaveTextContent("Số thập phân");
    expect(first).toHaveAttribute("aria-pressed", "true");
    expect(second).toHaveAttribute("aria-pressed", "false");

    await user.click(second);
    expect(await screen.findByText(/Chương Diện tích hình tam giác, hình thang/)).toBeInTheDocument();
    expect(getChildOverview).toHaveBeenLastCalledWith("4ACA86", AREA.chapter_id);
    expect(screen.getByRole("button", { name: AREA.title })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: DECIMALS.title })).toHaveAttribute("aria-pressed", "false");
  });

  it("opens on the chapter named in the link", async () => {
    const getChildOverview = vi.fn((_code: string, chapter?: string) =>
      Promise.resolve({ ...CHILD, chapter: chapter === AREA.chapter_id ? AREA : DECIMALS }),
    );
    renderApp(`/parent/4ACA86?chapter=${AREA.chapter_id}`, progressApi({ getChildOverview }));
    expect(await screen.findByText(/Chương Diện tích hình tam giác, hình thang/)).toBeInTheDocument();
    expect(getChildOverview).toHaveBeenCalledWith("4ACA86", AREA.chapter_id);
  });

  it("offers no choice when the tutor teaches one chapter only", async () => {
    const one = { ...CHILD, chapters: [DECIMALS] };
    renderApp("/parent/4ACA86", progressApi({ getChildOverview: () => Promise.resolve(one) }));
    await screen.findByRole("heading", { level: 1, name: "Tình hình học của An" });
    expect(screen.queryByRole("navigation", { name: "Chọn chương" })).not.toBeInTheDocument();
  });

  it("follows the linked child of the parent account on the chapter picked (ACC-1)", async () => {
    const parent: AuthUser = { user_id: "u-p", kind: "PARENT", display_name: "Mẹ An", child_id: "u-s" };
    const getMyChild = vi.fn((chapter?: string) =>
      Promise.resolve({ ...CHILD, chapter: chapter === AREA.chapter_id ? AREA : DECIMALS }),
    );
    const api = progressApi({
      getMyChild,
      auth: {
        config: () => Promise.resolve({ mode: "accounts", accounts: [] }),
        login: () => Promise.resolve(parent),
        register: () => Promise.resolve(parent),
        me: () => Promise.resolve(parent),
        switchTo: () => true,
        logout: () => undefined,
      },
    });
    const { user } = renderApp("/parent", api);
    await user.click(await screen.findByRole("button", { name: AREA.title }));
    expect(await screen.findByText(/Chương Diện tích hình tam giác, hình thang/)).toBeInTheDocument();
    expect(getMyChild).toHaveBeenNthCalledWith(1, undefined);
    expect(getMyChild).toHaveBeenLastCalledWith(AREA.chapter_id);
  });

  it("explains an unknown code and offers to enter it again", async () => {
    renderApp("/parent/ZZZZZZ", progressApi());
    expect(await screen.findByText(/Không tìm thấy học sinh có mã ZZZZZZ\./)).toHaveAttribute(
      "role",
      "status",
    );
    expect(screen.getByRole("link", { name: "Nhập lại mã" })).toHaveAttribute("href", "/parent");
  });
});

describe("student home dashboard (PART 27.1)", () => {
  it("shows the chapter in the student's two words, what to practise and the code for parents", async () => {
    renderApp("/student", progressApi());
    const map = await screen.findByRole("region", { name: "Bản đồ chương Số thập phân" });
    const states = within(map)
      .getAllByRole("listitem")
      .map((li) => li.textContent);
    expect(states).toEqual(
      expect.arrayContaining([
        "Phân số thập phânĐã nắm chắc",
        "Khái niệm số thập phânCần luyện thêm",
        "Giá trị theo hàngChưa học",
      ]),
    );
    expect(screen.getByRole("region", { name: "Cần luyện thêm" })).toHaveTextContent(
      "Khái niệm số thập phân",
    );
    expect(screen.getByRole("region", { name: "Con đã làm tốt" })).toHaveTextContent("Phân số thập phân");
    const code = screen.getByRole("region", { name: "Mã cho bố mẹ" });
    expect(code).toHaveTextContent("4ACA86");
    expect(within(code).getByRole("link", { name: "Mở trang phụ huynh" })).toHaveAttribute(
      "href",
      "/parent/4ACA86",
    );
  });
});
