import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { memoryStorage } from "../../test/memoryStorage";
import { renderApp, testApi } from "../../test/renderApp";

const seeded = () => testApi({ seed: true, storage: memoryStorage() });

function itemBlock(title: RegExp) {
  return screen.getByRole("region", { name: title });
}

describe("teacher transcript screen", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lists sessions, newest first, and opens the first one", async () => {
    renderApp("/teacher/sessions", seeded());
    const list = await screen.findByRole("navigation", { name: "Danh sách buổi học" });
    const links = within(list).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual([
      expect.stringContaining("Lan"),
      expect.stringContaining("Minh"),
    ]);
    expect(links[0]).toHaveAttribute("aria-current", "page");
    expect(links[1]).toHaveTextContent("08:00 29/09/2026 · 8/8 câu");
    expect(await screen.findByRole("heading", { level: 2, name: "Lan" })).toBeInTheDocument();
  });

  it("annotates every turn with the decision behind it", async () => {
    renderApp("/teacher/sessions", seeded());
    await screen.findByRole("heading", { level: 2, name: "Lan" });
    const cc02 = itemBlock(/Câu 2 · CC-02/);
    expect(within(cc02).getByText("Đang làm")).toBeInTheDocument();
    expect(cc02).toHaveTextContent("Lan: <");
    expect(within(cc02).getByText("Sai")).toBeInTheDocument();
    expect(within(cc02).getByText("DEC-M01 · Dài hơn thì lớn hơn (0,9)")).toBeInTheDocument();
    expect(within(cc02).getByText("Phản ví dụ")).toBeInTheDocument();
    expect(within(cc02).getByText("H2 · khái niệm")).toBeInTheDocument();
    expect(within(cc02).getByText("R-MISC-HIGH")).toBeInTheDocument();
    expect(screen.getByText("Dữ liệu giả lập")).toBeInTheDocument();
  });

  it("shows item results, the checker's reading of each answer and ungraded EXIT items", async () => {
    const { user } = renderApp("/teacher/sessions", seeded());
    await user.click(await screen.findByRole("link", { name: /Minh/ }));
    await screen.findByRole("heading", { level: 2, name: "Minh" });

    const gp01 = itemBlock(/Câu 3 · GP-01/);
    expect(within(gp01).getByText("Làm được nhờ gợi ý")).toBeInTheDocument();
    expect(gp01).toHaveTextContent("Gợi ý cao nhất: H2 (nhắc khái niệm)");
    expect(gp01).toHaveTextContent("Đọc là: 0,25 > 0,3"); // the checker reading, vi-VN decimals
    expect(within(gp01).getByText("Hỏi vì sao")).toBeInTheDocument();

    const ex01 = itemBlock(/Câu 7 · EX-01/);
    expect(within(ex01).getAllByText("Chưa chấm")).toHaveLength(2); // the item and the answer
    expect(within(ex01).getByText("Bài kiểm tra cuối buổi")).toBeInTheDocument();
    // Greeting, practice intro, assessment intro, summary: outside any item, in timeline order.
    const sessionLines = screen.getAllByLabelText("Lời mở đầu, chuyển hoạt động, tổng kết");
    expect(sessionLines).toHaveLength(4);
    expect(sessionLines[3]).toHaveTextContent("Hôm nay con đã làm 8 câu.");
  });

  it("recreates the demo data on request", async () => {
    const api = seeded();
    const { session_id } = await api.createDemoSession({ student_display_name: "Dũng" });
    await api.join(session_id);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    const { user } = renderApp(`/teacher/sessions/${session_id}`, api);
    expect(await screen.findByRole("heading", { level: 2, name: "Dũng" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tạo lại dữ liệu demo" }));

    const list = await screen.findByRole("navigation", { name: "Danh sách buổi học" });
    await waitFor(() => expect(within(list).queryByText("Dũng")).not.toBeInTheDocument());
    expect(within(list).getByText("Lan")).toBeInTheDocument();
  });

  it("says so when there is no session yet", async () => {
    renderApp("/teacher/sessions", testApi());
    expect(await screen.findAllByText("Chưa có buổi học nào.")).not.toHaveLength(0);
  });
});
