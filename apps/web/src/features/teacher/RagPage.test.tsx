import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SessionApi } from "../../api/client";
import type { RagMode, RagSearch, RagStatus } from "../../api/contract";
import { renderApp, testApi } from "../../test/renderApp";

const STATUS: RagStatus = {
  chunks: 48,
  by_source: { chapter: 47, document: 1 },
  by_kind: { theory: 16, method: 7, worked_example: 15, misconception_note: 9, source_passage: 1 },
  nodes: [
    { node_id: "KC-DEC-FRAC", name: "Phân số thập phân", chunks: 6 },
    { node_id: "KC-DEC-EQ", name: "Số thập phân bằng nhau", chunks: 7 },
  ],
  documents: [{ document_id: "d1", title: "Phiếu bài tập 1", status: "READ", passages: 1, tied_to_node: 1 }],
  semantic: "gemini-embedding-001",
  semantic_is_model: true,
  semantic_error: null,
  built_at: "2026-10-07T08:00:00Z",
};

const FOUND: RagSearch = {
  query: "sao thêm số 0 vào cuối mà số không đổi",
  node_id: "KC-DEC-EQ",
  mode: "question",
  grounded: true,
  grounding: "cosine 0.78 ≥ 0.65",
  semantic: "gemini-embedding-001",
  candidates: 30,
  elapsed_ms: 12.3,
  results: [
    {
      chunk_id: "KC-DEC-EQ:theory:T1",
      title: "Số thập phân bằng nhau · cách giảng T1 (đoạn dây)",
      kind: "theory",
      source: "chapter",
      node_id: "KC-DEC-EQ",
      node_name: "Số thập phân bằng nhau",
      document_id: null,
      page: null,
      approved: false,
      text: "Đoạn dây dài 0,2 m, tức là 2 dm.",
      bm25: 21.4,
      bm25_rank: 1,
      cosine: 0.78,
      cosine_rank: 1,
      distance: 0,
      fused: 0.0328,
      final: 0.0295,
      coverage: 0.61,
      reasons: ["bản nháp"],
    },
  ],
};

function ragApi(status: RagStatus = STATUS) {
  const searches: { query: string; nodeId?: string; mode: RagMode }[] = [];
  let rebuilt = 0;
  const api: SessionApi = {
    ...testApi(),
    rag: {
      status: () => Promise.resolve(status),
      rebuild: () => {
        rebuilt += 1;
        return Promise.resolve({ ...status, chunks: status.chunks + 1 });
      },
      search: (query, options) => {
        searches.push({ query, ...options });
        return Promise.resolve(FOUND);
      },
    },
  };
  return { api, searches, rebuilt: () => rebuilt };
}

describe("teacher RAG page (RAG-1)", () => {
  it("shows every source of the RAG and the embedding model", async () => {
    const { api, rebuilt } = ragApi();
    const { user } = renderApp("/teacher/rag", api);
    expect(await screen.findByRole("heading", { name: "Kho đoạn: 48 đoạn" })).toBeInTheDocument();
    expect(screen.getByText(/vector gemini-embedding-001/)).toBeInTheDocument();
    const chips = screen.getByRole("list", { name: "Theo nguồn và loại" });
    expect(chips).toHaveTextContent("Nội dung chương: 47");
    expect(chips).toHaveTextContent("Tài liệu giáo viên: 1");
    expect(chips).toHaveTextContent("Lý thuyết: 16");
    expect(screen.getByRole("table")).toHaveTextContent("Phiếu bài tập 1");

    await user.click(screen.getByRole("button", { name: "Dựng lại chỉ mục" }));
    expect(await screen.findByRole("heading", { name: "Kho đoạn: 49 đoạn" })).toBeInTheDocument();
    expect(rebuilt()).toBe(1);
  });

  it("says when the RAG runs on keywords only and has no teacher document yet", async () => {
    renderApp(
      "/teacher/rag",
      ragApi({ ...STATUS, semantic: "off", documents: [], by_source: { chapter: 47 } }).api,
    );
    expect(await screen.findByText(/chưa có khóa Gemini/)).toBeInTheDocument();
    expect(screen.getByText(/Chưa có tài liệu giáo viên/)).toBeInTheDocument();
  });

  it("runs a search in a node and shows every signal of the chosen passages", async () => {
    const { api, searches } = ragApi();
    const { user } = renderApp("/teacher/rag", api);
    await user.type(await screen.findByLabelText("Câu hỏi"), "sao thêm số 0 vào cuối mà số không đổi");
    await user.selectOptions(screen.getByLabelText("Học sinh đang ở bài"), "KC-DEC-EQ");
    await user.click(screen.getByRole("button", { name: "Tra cứu" }));
    await waitFor(() =>
      expect(searches).toEqual([
        { query: "sao thêm số 0 vào cuối mà số không đổi", nodeId: "KC-DEC-EQ", mode: "question" },
      ]),
    );
    expect(await screen.findByText(/Có căn cứ: gia sư được dựa vào các đoạn này/)).toBeInTheDocument();
    const [card] = within(screen.getByRole("list", { name: "Các đoạn được chọn" })).getAllByRole("listitem");
    expect(card).toHaveTextContent("1. Số thập phân bằng nhau · cách giảng T1 (đoạn dây)");
    expect(card).toHaveTextContent("21,4 · hạng 1");
    expect(card).toHaveTextContent("0,78 · hạng 1");
    expect(card).toHaveTextContent("0 bước");
    expect(card).toHaveTextContent("61%");
    expect(card).toHaveTextContent("Xếp hạng lại: bản nháp");
  });

  it("has a tab in the teacher header", async () => {
    renderApp("/teacher/rag", ragApi().api);
    expect(await screen.findByRole("link", { name: "RAG" })).toHaveAttribute("aria-current", "page");
  });
});
