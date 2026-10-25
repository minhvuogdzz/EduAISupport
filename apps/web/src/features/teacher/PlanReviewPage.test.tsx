import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SessionApi } from "../../api/client";
import type { TeachingPlanReview } from "../../api/contract";
import { renderApp, testApi } from "../../test/renderApp";

function plan(overrides: Partial<TeachingPlanReview> = {}): TeachingPlanReview {
  return {
    chapter_id: "math-g5-decimals",
    status: "DRAFT",
    current: null,
    built_at: "2026-10-12T08:00:00Z",
    content: {
      chapter_id: "math-g5-decimals",
      title: "Số thập phân",
      version: "0.1.0",
      status: "DRAFT",
      source: "tài liệu của giáo viên",
      relations: [],
      misconceptions: [],
      nodes: [
        {
          node_id: "STP-T04",
          name: "So sánh hai số thập phân",
          layer: "BASIC",
          description: "Bé so sánh được hai số thập phân.",
          home_tip: "",
          theory: [
            {
              id: "T1",
              representation: "Bảng hàng",
              text: "Đặt 7,25 và 7,3 vào bảng hàng.",
              ask: "Hai số có cùng phần nguyên thì so sánh hàng nào trước?",
              reply: "So sánh hàng phần mười trước.",
              accept: ["hàng phần mười"],
            },
          ],
          method: { rule: "So sánh phần nguyên trước.", steps: ["So sánh phần nguyên trước."] },
          worked_examples: [],
          retell: { prompt: "Con nói lại cách so sánh?", key_ideas: [["phần nguyên trước"]] },
          pass_rule: { min_mastery: 75 },
          items: [
            {
              item_id: "STP-PH04-2",
              stage: "Luyện tập",
              purpose: "PRACTICE",
              cognitive_level: "B",
              difficulty: 0.45,
              stem: "6,44 …… 6,466",
              answer_type: "compare",
              answer: "6,44 < 6,466",
              hints: [{ level: 1, target: "TASK", text: "Phần nguyên của hai số có bằng nhau không?" }],
              worked_solution: [],
              explanation: null,
              wrong_answers: {},
            },
          ],
        },
      ],
    },
    sources: { "STP-T04": ["Giáo án, tiết 4, trang 3", "Lý thuyết, Bài 11 · So sánh, trang 3"] },
    items: {
      "STP-PH04-2": {
        status: "VERIFIED",
        findings: [],
        page: 2,
        document_id: "d1",
        answer_document_id: "d2",
        ai_hints: [1],
      },
    },
    left_out: [
      {
        item_id: "STP-BT-02a",
        reason: "CONFLICT",
        status: "CONFLICT",
        findings: [{ check: "CONVERSION", ok: false, detail: "0,9 = 7/10" }],
        page: 1,
        document_id: "d1",
        answer_document_id: "d2",
        ai_hints: [],
        stem: "Viết thành phân số thập phân:\na) 0,9 = ……",
        answer: "7/10",
      },
    ],
    decisions: {},
    assessment: [],
    review: { approved_nodes: [], waiting_nodes: ["STP-T04"], blockers: ["STP-T04: chưa duyệt"] },
    drafted: { hints: 1, parts: 1 },
    ...overrides,
  };
}

function plansApi(review: TeachingPlanReview = plan()) {
  const decisions: { target: string; action: string; value?: unknown }[] = [];
  let published = 0;
  const api: SessionApi = {
    ...testApi(),
    plans: {
      view: () => Promise.resolve(review),
      build: () => Promise.resolve({}),
      decide: (_chapter, target, action, value) => {
        decisions.push({ target, action, value });
        return Promise.resolve({});
      },
      undo: () => Promise.resolve({}),
      publish: () => {
        published += 1;
        return Promise.resolve({});
      },
    },
  };
  return { api, decisions, published: () => published };
}

describe("PlanReviewPage (INGEST-4)", () => {
  it("shows a period with its sources, the AI's hints and what waits before publishing", async () => {
    const { api } = plansApi();
    renderApp("/teacher/plans/math-g5-decimals", api);
    expect(await screen.findByRole("heading", { name: "So sánh hai số thập phân" })).toBeInTheDocument();
    expect(screen.getByText("Giáo án, tiết 4, trang 3")).toBeInTheDocument();
    expect(screen.getByText("AI soạn")).toBeInTheDocument();
    expect(screen.getByText("đáp án đã kiểm")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Phát hành cho gia sư dạy" })).toBeDisabled();
    expect(screen.getByText("Còn 1 việc trước khi phát hành")).toBeInTheDocument();
  });

  it("records the teacher's decisions: approve a period, approve or rewrite a hint, fix a misread answer", async () => {
    const { api, decisions } = plansApi();
    const { user } = renderApp("/teacher/plans/math-g5-decimals", api);
    await user.click(await screen.findByRole("button", { name: "Duyệt bài này" }));
    await user.click(screen.getByRole("button", { name: "Duyệt" }));
    const card = screen.getByText("STP-BT-02a").closest("div")!.parentElement!;
    await user.click(within(card).getByRole("button", { name: "Sửa đáp án" }));
    const input = within(card).getByRole("textbox", { name: "Đáp án" });
    await user.clear(input);
    await user.type(input, "9/10");
    await user.click(within(card).getByRole("button", { name: "Lưu" }));
    await waitFor(() =>
      expect(decisions).toEqual([
        { target: "node:STP-T04", action: "approve", value: undefined },
        { target: "hint:STP-PH04-2:H1", action: "approve", value: undefined },
        { target: "item:STP-BT-02a/answer", action: "edit", value: "9/10" },
      ]),
    );
  });

  it("lets the teacher rewrite the period's why question and remove a counterexample (FIX-3)", async () => {
    const base = plan();
    const node = {
      ...base.content.nodes[0],
      verify_prompt: "Đúng rồi! Vì sao con so sánh phần nguyên trước?",
    };
    const mistake = {
      id: "STP-L4",
      kc_id: "STP-T04",
      name: "Số nào nhiều chữ số hơn thì lớn hơn",
      description: "",
      severity: "MAJOR",
      counter_examples: ["0,5 và 0,45: số nào lớn hơn?"],
    };
    const review = plan({
      content: { ...base.content, nodes: [node], misconceptions: [mistake] },
      ai_verify: ["STP-T04"],
    });
    const { api, decisions } = plansApi(review);
    const { user } = renderApp("/teacher/plans/math-g5-decimals", api);
    expect(
      await screen.findByText("Vì sao con so sánh phần nguyên trước?", { exact: false }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("AI soạn")).toHaveLength(2); // the hint and the why question
    await user.click(screen.getByRole("button", { name: "Sửa câu hỏi vì sao" }));
    const input = screen.getByRole("textbox", { name: "Câu hỏi vì sao" });
    await user.clear(input);
    await user.type(input, "Đúng rồi! Con so sánh phần nào trước?");
    await user.click(screen.getByRole("button", { name: "Lưu" }));
    await user.click(screen.getByRole("button", { name: "Bỏ phản ví dụ" }));
    await waitFor(() =>
      expect(decisions).toEqual([
        {
          target: "node:STP-T04/verify/prompt",
          action: "edit",
          value: "Đúng rồi! Con so sánh phần nào trước?",
        },
        { target: "misconception:STP-L4/counter_examples", action: "reject", value: undefined },
      ]),
    );
  });

  it("takes an emptied why question as removing it: the tutor asks the general one (REFORM 4.4)", async () => {
    const base = plan();
    const node = {
      ...base.content.nodes[0],
      verify_prompt: "Đúng rồi! Vì sao con so sánh phần nguyên trước?",
    };
    const { api, decisions } = plansApi(plan({ content: { ...base.content, nodes: [node] } }));
    const { user } = renderApp("/teacher/plans/math-g5-decimals", api);
    await user.click(await screen.findByRole("button", { name: "Sửa câu hỏi vì sao" }));
    await user.clear(screen.getByRole("textbox", { name: "Câu hỏi vì sao" }));
    await user.click(screen.getByRole("button", { name: "Lưu" }));

    // the API takes no empty edit ("an edit needs a value"): the same decision as "Loại câu hỏi vì sao"
    await waitFor(() =>
      expect(decisions).toEqual([
        { target: "node:STP-T04/verify/prompt", action: "reject", value: undefined },
      ]),
    );
  });

  it("changes nothing when a field without a default is emptied, or the why question was empty", async () => {
    const { api, decisions } = plansApi();
    const { user } = renderApp("/teacher/plans/math-g5-decimals", api);
    await user.click(await screen.findByRole("button", { name: "Sửa câu hỏi vì sao" })); // it has no text
    await user.click(screen.getByRole("button", { name: "Lưu" }));
    await user.click(screen.getByRole("button", { name: "Sửa quy tắc" }));
    await user.clear(screen.getByRole("textbox", { name: "Quy tắc" }));
    await user.click(screen.getByRole("button", { name: "Lưu" }));
    expect(screen.getByText("Quy tắc:", { exact: false })).toBeInTheDocument(); // back to the text view
    expect(decisions).toEqual([]);
  });

  it("publishes once nothing waits", async () => {
    const ready = plan({ review: { approved_nodes: ["STP-T04"], waiting_nodes: [], blockers: [] } });
    const { api, published } = plansApi(ready);
    const { user } = renderApp("/teacher/plans/math-g5-decimals", api);
    expect(await screen.findByText(/✓ 1\. So sánh hai số thập phân/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Phát hành cho gia sư dạy" }));
    await waitFor(() => expect(published()).toBe(1));
  });
});
