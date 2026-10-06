import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { NODES, RELATIONS } from "../../test/teachingFixtures";
import { KnowledgeMap } from "./KnowledgeMap";

describe("knowledge map", () => {
  it("says each node's status and level in words, never by color alone", () => {
    render(<KnowledgeMap nodes={NODES} relations={RELATIONS} title="Bản đồ" />);
    expect(screen.getByRole("group", { name: "Bản đồ" })).toBeInTheDocument();
    const items = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toEqual([
      "Phân số thập phân: Đã qua, Vận dụng được",
      "Khái niệm số thập phân: Đang học, Làm theo mẫu",
      "So sánh hai số thập phân: Chưa mở",
    ]);
    expect(screen.queryAllByRole("button")).toHaveLength(0); // the student map is not interactive
  });

  it("lets the teacher pick a node and shows M instead of the level", async () => {
    const onSelect = vi.fn();
    const nodes = NODES.map((node, i) => ({ ...node, mastery: [75.3, 58.4, null][i] }));
    render(
      <KnowledgeMap
        nodes={nodes}
        relations={RELATIONS}
        title="Cây"
        showMastery
        selectedId="KC-DEC-FRAC"
        onSelect={onSelect}
      />,
    );
    const frac = screen.getByRole("button", { name: "Phân số thập phân: Đã qua, M 75,3" });
    expect(frac).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(
      screen.getByRole("button", { name: "So sánh hai số thập phân: Chưa mở, chưa có điểm" }),
    );
    expect(onSelect).toHaveBeenCalledWith("KC-DEC-CMP");
  });
});
