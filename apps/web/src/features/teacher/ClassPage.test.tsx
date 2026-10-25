import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type SessionApi } from "../../api/client";
import type {
  ClassOverview,
  Dimension,
  MasteryCell,
  TeacherNodeDetail,
  TeacherStudentView,
} from "../../api/contract";
import { RECOMMENDATION_LABEL } from "../../components/labels";
import { renderApp, testApi } from "../../test/renderApp";

const FRAC = "KC-DEC-FRAC";
const CONCEPT = "KC-DEC-CONCEPT";
const COMPARE = "KC-DEC-COMPARE";
const NODES = [
  { node_id: FRAC, name: "Phân số thập phân", layer: "BASIC", order: 0, min_mastery: 75 },
  { node_id: COMPARE, name: "So sánh hai số thập phân", layer: "IMPLEMENT", order: 2, min_mastery: 75 },
  { node_id: CONCEPT, name: "Khái niệm số thập phân", layer: "BASIC", order: 1, min_mastery: 75 },
] as const;

function cell(node_id: string, mastery: number | null, extra: Partial<MasteryCell> = {}): MasteryCell {
  return {
    node_id,
    mastery,
    confidence: mastery === null ? 0 : 55,
    level: 0,
    state: "LEARNING",
    insufficient_data: false,
    passed: false,
    status: "AVAILABLE",
    active_misconceptions: 0,
    ...extra,
  };
}

const CLASS: ClassOverview = {
  chapter: { chapter_id: "math-g5-decimals", title: "Số thập phân" },
  nodes: [...NODES],
  students: [
    {
      student_id: "an",
      display_name: "An",
      sessions: { total: 2, completed: 1, unfinished: 1, minutes: 20 },
      last_active_at: "2026-10-06T08:00:00Z",
      passed: 1,
      overall: { mastery: 71.6, confidence: 37.5, level: 3, coverage: 66.7 },
      cells: [
        cell(FRAC, 82.3, { passed: true, status: "PASSED" }),
        cell(CONCEPT, 61, { confidence: 20, insufficient_data: true, status: "CURRENT" }),
        cell(COMPARE, null),
      ],
      attention: [],
    },
    {
      student_id: "bao",
      display_name: "Bảo",
      sessions: { total: 1, completed: 0, unfinished: 1, minutes: 5 },
      last_active_at: "2026-10-06T09:00:00Z",
      passed: 0,
      overall: { mastery: 35.4, confidence: 40, level: 1, coverage: 33.3 },
      cells: [
        cell(FRAC, 35.4, { confidence: 40, active_misconceptions: 1, status: "CURRENT" }),
        cell(CONCEPT, null),
        cell(COMPARE, null),
      ],
      attention: [
        { kind: "SAFETY", session_id: "s-bao-1", at: "2026-10-06T09:05:00Z", count: 1 },
        { kind: "MISCONCEPTION", node_id: FRAC, misconception_id: "FRAC-M01", count: 2 },
      ],
    },
  ],
  by_node: [
    { node_id: FRAC, mean_mastery: 58.9, students: 2, passed: 1 },
    { node_id: CONCEPT, mean_mastery: 61, students: 1, passed: 0 },
    { node_id: COMPARE, mean_mastery: null, students: 0, passed: 0 },
  ],
  misconceptions: [
    {
      id: "FRAC-M01",
      name: "Quên chữ số 0 giữ chỗ",
      node_id: FRAC,
      severity: "CRITICAL",
      count: 3,
      share: 75,
      students: 1,
      active_students: 1,
      recent: 3,
    },
    {
      id: "CONCEPT-M01",
      name: "Nhầm phần nguyên với phần thập phân",
      node_id: CONCEPT,
      severity: "NORMAL",
      count: 1,
      share: 25,
      students: 1,
      active_students: 0,
      recent: 1,
    },
  ],
  kpis: {
    students: 2,
    active_this_week: 2,
    sessions: 3,
    minutes: 25,
    passed: 1,
    cells: 6,
    mean_mastery: 53.5,
    attention: 1,
  },
};

const DIMS: Record<Dimension, number | null> = {
  C: 52.5,
  R: 30.2,
  A: null,
  T: null,
  I: 61.7,
  S: null,
  D: null,
};

function detail(node_id: string, extra: Partial<TeacherNodeDetail>): TeacherNodeDetail {
  const info = NODES.find((n) => n.node_id === node_id)!;
  return {
    ...info,
    ...cell(node_id, null),
    group: "NOT_STARTED",
    dimensions: Object.fromEntries(
      Object.keys(DIMS).map((d) => [d, { value: 50, n_eff: 0, in_mastery: false }]),
    ) as TeacherNodeDetail["dimensions"],
    items: 0,
    solved: 0,
    attempts: 0,
    hints: 0,
    seconds: null,
    misconceptions: [],
    trend: [],
    direction: null,
    recommendation: "DIAGNOSE",
    ...extra,
  };
}

const BAO: TeacherStudentView = {
  student_id: "bao",
  display_name: "Bảo",
  chapter: CLASS.chapter,
  relations: [
    { source: FRAC, target: CONCEPT, type: "PREREQUISITE" },
    { source: CONCEPT, target: COMPARE, type: "APPLICATION" },
  ],
  sessions: { total: 1, completed: 0, unfinished: 1, minutes: 5 },
  session_list: [
    {
      session_id: "s-1",
      started_at: "2026-10-06T08:30:00Z",
      minutes: 5,
      lifecycle_state: "ACTIVE",
      passed_names: [],
    },
  ],
  last_active_at: "2026-10-06T09:00:00Z",
  overall: { mastery: 35.4, confidence: 40, level: 1, coverage: 33.3, passed: 0, total: 3 },
  dimensions: Object.fromEntries(
    Object.entries(DIMS).map(([d, v]) => [d, { value: v, n_eff: v === null ? 0 : 2 }]),
  ) as TeacherStudentView["dimensions"],
  strengths: [],
  weaknesses: ["R", "C"],
  nodes: [
    detail(FRAC, {
      ...cell(FRAC, 35.4, {
        confidence: 40,
        level: 1,
        state: "RECOGNIZED",
        active_misconceptions: 1,
        status: "CURRENT",
      }),
      group: "WEAK",
      items: 3,
      solved: 1,
      attempts: 5,
      hints: 4,
      seconds: 42,
      misconceptions: [
        { id: "FRAC-M01", name: "Quên chữ số 0 giữ chỗ", severity: "CRITICAL", count: 2, status: "ACTIVE" },
      ],
      trend: [
        { at: "2026-10-05T08:00:00Z", mastery: 61.7 },
        { at: "2026-10-05T08:05:00Z", mastery: 46.8 },
        { at: "2026-10-06T08:40:00Z", mastery: 35.4 },
      ],
      direction: "DOWN",
      recommendation: "EXPLAIN",
    }),
    detail(CONCEPT, {}),
    detail(COMPARE, {}),
  ],
  timeline: [
    { date: "2026-10-05", mastery: 46.8 },
    { date: "2026-10-06", mastery: 35.4 },
  ],
  velocity: null,
  activity: [
    { date: "2026-10-05", independent: 0, supported: 1, worked: 0, unresolved: 0, hints: 1, passed: 0 },
    { date: "2026-10-06", independent: 0, supported: 0, worked: 1, unresolved: 1, hints: 3, passed: 0 },
  ],
  attention: [{ kind: "MISCONCEPTION", node_id: FRAC, misconception_id: "FRAC-M01", count: 2 }],
};

function teacherApi(): SessionApi {
  return {
    ...testApi(),
    getClassOverview: () => Promise.resolve(CLASS),
    getStudentReport: (id) => (id === "bao" ? Promise.resolve(BAO) : Promise.reject(new Error("unknown"))),
  };
}

describe("class dashboard (PART 27.1, khung Toán §45, §46, §28)", () => {
  it("draws the Student × KC heatmap in the zones of §25, with the class row of §45", async () => {
    renderApp("/teacher", teacherApi());
    const table = await screen.findByRole("table", { name: /Bản đồ nhiệt học sinh và bài/ });
    // Concepts first, then their applications.
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers.slice(0, 4)).toEqual(["Học sinh", "Khái niệm", "Vận dụng khái niệm", "Tổng (§23)"]);
    expect(headers.slice(4)).toEqual([
      "Phân số thập phân",
      "Khái niệm số thập phân",
      "So sánh hai số thập phân",
    ]);

    const passed = within(table).getByRole("link", {
      name: "An, Phân số thập phân: M 82,3, độ tin cậy 55, đã qua bài",
    });
    expect(passed).toHaveClass("bg-emerald-300");
    expect(passed).toHaveTextContent("82");
    // the report opens on the chapter of this class view (REFORM 4.4), on the KC of the cell
    expect(passed).toHaveAttribute("href", `/teacher/students/an?chapter=math-g5-decimals&node=${FRAC}`);
    const unsure = within(table).getByRole("link", {
      name: /An, Khái niệm số thập phân: M 61.*chưa đủ dữ liệu/,
    });
    expect(unsure).toHaveClass("bg-yellow-300", "hatched");
    expect(
      within(table).getByRole("link", {
        name: "Bảo, Phân số thập phân: M 35,4, độ tin cậy 40, 1 lỗi đang mắc",
      }),
    ).toHaveClass("bg-red-600");
    expect(
      within(table).getByRole("link", { name: "Bảo, Khái niệm số thập phân: chưa có bằng chứng" }),
    ).toHaveTextContent("–");
    const classRow = within(table).getByRole("rowheader", { name: "Cả lớp (§45)" }).closest("tr")!;
    expect(classRow).toHaveTextContent("582 em611 em–0 em");
  });

  it("opens a student's report on the chapter of the class view, not on the first one", async () => {
    const area = {
      chapter_id: "math-g5-area-triangle-trapezoid",
      title: "Diện tích hình tam giác, hình thang",
    };
    const getStudentReport = vi.fn((id: string, chapter?: string) =>
      id === "bao" && chapter ? Promise.resolve(BAO) : Promise.reject(new Error("unknown")),
    );
    const api: SessionApi = {
      ...teacherApi(),
      getClassOverview: () => Promise.resolve({ ...CLASS, chapter: area }),
      getStudentReport,
    };
    const { user } = renderApp(`/teacher?chapter=${area.chapter_id}`, api);
    const table = await screen.findByRole("table", { name: /Bản đồ nhiệt học sinh và bài/ });
    const name = within(within(table).getByRole("rowheader", { name: /^Bảo/ })).getByRole("link");
    expect(name).toHaveAttribute("href", `/teacher/students/bao?chapter=${area.chapter_id}`);
    await user.click(name);

    expect(await screen.findByRole("heading", { level: 1, name: "Học sinh Bảo" })).toBeInTheDocument();
    expect(getStudentReport).toHaveBeenCalledWith("bao", area.chapter_id);
  });

  it("sorts the students with the lowest score first", async () => {
    const { user } = renderApp("/teacher", teacherApi());
    const table = await screen.findByRole("table");
    const names = () =>
      within(table)
        .getAllByRole("rowheader")
        .map((h) => h.textContent);
    expect(names()[0]).toMatch(/^An/);
    await user.click(screen.getByRole("button", { name: "Điểm thấp trước" }));
    expect(names()[0]).toMatch(/^Bảo/);
  });

  it("shows the misconception chart of §28 and the students who need attention", async () => {
    renderApp("/teacher", teacherApi());
    const mistakes = await screen.findByRole("region", { name: "Lỗi sai phổ biến của lớp" });
    expect(mistakes).toHaveTextContent("Lỗi tái diễn nhiều nhất: Quên chữ số 0 giữ chỗ");
    expect(mistakes).toHaveTextContent("Xuất hiện: 3 lần / 14 ngày");
    expect(mistakes).toHaveTextContent("Mức độ: Cần can thiệp");
    expect(
      within(mistakes).getByRole("img", { name: "Quên chữ số 0 giữ chỗ: 75% số lần phát hiện lỗi" }),
    ).toBeInTheDocument();
    expect(mistakes).toHaveTextContent("25% · 1 lần");

    const attention = screen.getByRole("region", { name: "Học sinh cần chú ý" });
    expect(within(attention).getByRole("link", { name: "Bảo" })).toHaveAttribute(
      "href",
      "/teacher/students/bao?chapter=math-g5-decimals",
    );
    expect(attention).toHaveTextContent("Lặp lại lỗi “Quên chữ số 0 giữ chỗ” (2 lần)");
    // SAFE-1: a worrying message comes first and opens the session where it was said
    expect(within(attention).getByRole("link", { name: /Con nói điều đáng lo/ })).toHaveAttribute(
      "href",
      "/teacher/sessions/s-bao-1",
    );
    expect(screen.getByText("Cần chú ý").parentElement?.parentElement).toHaveTextContent("1");
  });

  it("lets the teacher mark a worrying conversation read, then reloads the list (SAFE-1)", async () => {
    const reviewed: string[] = [];
    const api: SessionApi = {
      ...teacherApi(),
      getClassOverview: () =>
        Promise.resolve({
          ...CLASS,
          students: CLASS.students.map((s) => ({
            ...s,
            attention: s.attention.filter((r) => !(r.session_id && reviewed.includes(r.session_id))),
          })),
        }),
      markSafetyReviewed: (sessionId) => {
        reviewed.push(sessionId);
        return Promise.resolve({
          session_id: sessionId,
          through_sequence_no: 7,
          reviewed_at: "2026-10-06T10:00:00Z",
          reviewed_by: "1",
        });
      },
    };
    const { user } = renderApp("/teacher", api);
    const attention = await screen.findByRole("region", { name: "Học sinh cần chú ý" });
    await user.click(within(attention).getByRole("button", { name: "Cô đã xem hội thoại đáng lo của Bảo" }));
    expect(reviewed).toEqual(["s-bao-1"]);
    await waitFor(() => expect(attention).not.toHaveTextContent("Con nói điều đáng lo"));
    expect(attention).toHaveTextContent("Lặp lại lỗi");
  });

  it("explains that the class view needs the real server with the mock API", async () => {
    renderApp("/teacher", testApi());
    expect(await screen.findByRole("status")).toHaveTextContent("Bảng theo dõi lớp cần máy chủ thật");
    expect(screen.getByRole("link", { name: "Xem từng buổi học" })).toHaveAttribute(
      "href",
      "/teacher/sessions",
    );
  });
});

describe("student report for the teacher (khung Toán §23, §24, §27, §43, §56, §57)", () => {
  it("shows the gauge with confidence, the radar of §24 and the §43 groups", async () => {
    renderApp("/teacher/students/bao", teacherApi());
    expect(await screen.findByRole("heading", { level: 1, name: "Học sinh Bảo" })).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Mức độ hiểu tổng thể: M 35,4, vùng đỏ, mức 1 Nhận biết" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("img", { name: "Độ tin cậy 40 trên 100" }).length).toBeGreaterThan(0);
    const radar = screen.getByRole("img", { name: /^Biểu đồ radar 6 chiều/ });
    expect(radar).toHaveAccessibleName(expect.stringContaining("Lập luận 30,2"));
    expect(radar).toHaveAccessibleName(expect.stringContaining("Ghi nhớ chưa đủ dữ liệu"));
    expect(radar).not.toHaveAccessibleName(expect.stringContaining("Phát hiện lỗi")); // D is beside the radar

    const summary = screen.getByRole("region", { name: "Nhận định" });
    expect(summary).toHaveTextContent("Điểm yếu: Lập luận (30,2), Làm đúng (52,5)");
    expect(summary).toHaveTextContent("Rủi ro: Phân số thập phân");
    expect(summary).toHaveTextContent("✕ Còn yếu: Phân số thập phân");
  });

  it("keeps the chapter on the way back to the class when the student has no session on it", async () => {
    const api: SessionApi = {
      ...teacherApi(),
      getStudentReport: () => Promise.reject(new ApiError(404, "NOT_FOUND", "no session on the chapter")),
    };
    renderApp("/teacher/students/bao?chapter=math-g5-area-triangle-trapezoid", api);
    expect(await screen.findByText(/Em này chưa học buổi nào của chương\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Về bảng theo dõi lớp" })).toHaveAttribute(
      "href",
      "/teacher?chapter=math-g5-area-triangle-trapezoid",
    );
  });

  it("opens on the KC of the link with its §57 detail, and switches KC from the groups", async () => {
    const { user } = renderApp(`/teacher/students/bao?node=${FRAC}`, teacherApi());
    const kc = await screen.findByRole("region", { name: "Phân số thập phân" });
    expect(kc).toHaveTextContent("61,7 → 46,8 → 35,4↘ Suy giảm");
    expect(kc).toHaveTextContent(RECOMMENDATION_LABEL.EXPLAIN);
    expect(kc).toHaveTextContent("Quên chữ số 0 giữ chỗ2 lần · đang mắc · nghiêm trọng");
    expect(within(kc).getByText("Lần trả lời").nextSibling).toHaveTextContent("5");
    expect(within(kc).getByText("TB mỗi câu").nextSibling).toHaveTextContent("42 giây");

    await user.click(
      within(screen.getByRole("region", { name: "Nhận định" })).getByRole("button", {
        name: "Khái niệm số thập phân",
      }),
    );
    const other = await screen.findByRole("region", { name: "Khái niệm số thập phân" });
    expect(other).toHaveTextContent("Chưa có bằng chứng");
    expect(other).toHaveTextContent(RECOMMENDATION_LABEL.DIAGNOSE);
  });

  it("draws the timeline of §27 and the activity of §56, with the same data for screen readers", async () => {
    renderApp("/teacher/students/bao", teacherApi());
    expect(
      await screen.findByRole("img", { name: "Điểm hiểu bài tổng của chương theo từng ngày học" }),
    ).toBeInTheDocument();
    const inList = (text: string) => screen.getAllByText(text).some((el) => el.tagName === "LI");
    expect(inList("06/10: M 35,4")).toBe(true); // the SVG point has the same words as its tooltip
    expect(inList("06/10: 1 cần làm mẫu, 1 chưa giải quyết; 3 gợi ý")).toBe(true);
    expect(screen.getByRole("link", { name: "Bộ não gia sư và hội thoại" })).toHaveAttribute(
      "href",
      "/teacher/sessions/s-1",
    );
  });
});
