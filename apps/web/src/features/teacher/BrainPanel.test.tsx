import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { report } from "../../test/teachingFixtures";
import { BrainPanel } from "./BrainPanel";

describe("tutor's reasoning for the teacher (M1-7)", () => {
  it("opens on the current node: score, pass rule, misconception, evidence, decisions", () => {
    render(<BrainPanel report={report()} />);
    const detail = screen.getByRole("region", { name: "Khái niệm số thập phân" });
    expect(within(detail).getAllByText("58,4")).toHaveLength(2); // the score, and the chart's last point
    expect(within(detail).getAllByText("ngưỡng qua bài 75")).toHaveLength(2); // under the score, on the chart
    expect(within(detail).getByText("còn thiếu 4")).toBeInTheDocument();
    expect(within(detail).getByText(/Bỏ chữ số 0 ngay sau dấu phẩy/)).toBeInTheDocument();
    const rows = within(within(detail).getByRole("table")).getAllByRole("row");
    expect(rows).toHaveLength(3); // header + two pieces of evidence, newest first
    expect(rows[1]).toHaveTextContent("#41KN-CP-01C Làm đúng− trừ0,55kết quả câu");
    expect(
      screen.getByRole("img", { name: "Điểm M của bài Khái niệm số thập phân qua từng lượt" }),
    ).toBeInTheDocument();
    const decisions = screen.getByRole("region", { name: "Quyết định của cô (2)" });
    expect(within(decisions).getAllByRole("listitem")[0]).toHaveTextContent("N-TEACHGiảng lý thuyết");
  });

  it("shows another node when the teacher picks it on the map", async () => {
    render(<BrainPanel report={report()} />);
    await userEvent.click(screen.getByRole("button", { name: "Phân số thập phân: Đã qua, M 75,3" }));
    const detail = screen.getByRole("region", { name: "Phân số thập phân" });
    expect(within(detail).getByText("đủ điều kiện")).toBeInTheDocument();
    expect(within(detail).getByText("Làm đúng bài vận dụng").closest("li")).toHaveTextContent("Đạt:");
    expect(within(detail).getByText("Chưa có bằng chứng nào cho bài này.")).toBeInTheDocument();
  });
});
