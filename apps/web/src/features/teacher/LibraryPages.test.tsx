import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SessionApi } from "../../api/client";
import type { ChapterContent, TeacherDocument } from "../../api/contract";
import { renderApp, testApi } from "../../test/renderApp";

const DOC: TeacherDocument = {
  document_id: "d1",
  title: "SGK Toán 5 · Số thập phân",
  kind: "SGK",
  chapter_id: "math-g5-decimals",
  filename: "sgk.pdf",
  content_type: "application/pdf",
  size: 204800,
  uploaded_at: "2026-10-07T08:00:00Z",
  status: "READ",
  method: "pdf-text",
  pages: 12,
  chars: 15342,
  error: null,
};

const CONTENT: ChapterContent = {
  chapter_id: "math-g5-decimals",
  title: "Số thập phân",
  version: "0.1.0",
  status: "DRAFT",
  source: "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml",
  relations: [],
  misconceptions: [
    {
      id: "FRAC-M01",
      kc_id: "KC-DEC-FRAC",
      name: "Quên chữ số 0 giữ chỗ",
      description: "",
      severity: "CRITICAL",
      counter_examples: [],
    },
  ],
  nodes: [
    {
      node_id: "KC-DEC-FRAC",
      name: "Phân số thập phân",
      layer: "BASIC",
      description: "Phân số có mẫu số là 10, 100, 1000...",
      home_tip: "Cùng con chia một chiếc bánh thành 10 phần.",
      theory: [
        {
          id: "T1",
          representation: "hình vuông chia ô",
          text: "Cô chia một hình vuông thành 10 phần.",
          ask: "Nếu tô màu 4 ô trong 100 ô thì phần tô màu là phân số nào?",
          reply: "Tô 4 ô trong 100 ô thì phần tô màu là 4/100.",
          accept: ["4/100", "0,04"],
        },
      ],
      method: { rule: "Đếm chữ số 0 của mẫu số.", steps: ["Đếm chữ số 0", "Viết tử số"] },
      worked_examples: [],
      retell: { prompt: "Con nói lại giúp cô?", key_ideas: [["mẫu số là 10"]] },
      items: [
        {
          item_id: "TP-PR-01",
          stage: "Luyện tập",
          purpose: "PRACTICE",
          cognitive_level: "B",
          difficulty: 0.3,
          stem: "Viết phân số 9/10 dưới dạng số thập phân.",
          answer_type: "numeric",
          answer: "0,9",
          hints: [{ level: 1, target: "TASK", text: "Mình cần viết 9/10 thành số thập phân?" }],
          worked_solution: ["Mẫu số là 10 nên phần thập phân có một chữ số."],
          explanation: null,
          wrong_answers: { "0,09": "FRAC-M01" },
        },
      ],
      pass_rule: { min_mastery: 75 },
    },
  ],
};

function libraryApi() {
  const uploads: { name: string; title: string; kind: string; chapterId: string }[] = [];
  const api: SessionApi = {
    ...testApi(),
    library: {
      list: () => Promise.resolve([DOC]),
      get: () => Promise.resolve({ ...DOC, text: "[Trang 1]\nBài 8. Số thập phân" }),
      upload: (file, meta) => {
        uploads.push({ name: file.name, ...meta });
        return Promise.resolve({ ...DOC, document_id: "d2", title: meta.title || file.name });
      },
      remove: () => Promise.resolve(),
      original: () => Promise.resolve(new Blob(["pdf"])),
      chapters: () =>
        Promise.resolve([
          { chapter_id: "math-g5-decimals", title: "Số thập phân", status: "DRAFT", nodes: 7, items: 31 },
        ]),
      chapter: () => Promise.resolve(CONTENT),
    },
  };
  return { api, uploads };
}

describe("teacher library and lesson content (DOC-1)", () => {
  it("lists the documents and uploads a new one with its kind and chapter", async () => {
    const { api, uploads } = libraryApi();
    const { user } = renderApp("/teacher/documents", api);
    const table = await screen.findByRole("table");
    expect(within(table).getByRole("link", { name: "SGK Toán 5 · Số thập phân" })).toHaveAttribute(
      "href",
      "/teacher/documents/d1",
    );
    expect(table).toHaveTextContent("Đã đọc");

    await user.upload(screen.getByLabelText("File (PDF, DOCX, ảnh…)"), new File(["x"], "phieu-1.docx"));
    await user.type(screen.getByLabelText("Tên tài liệu"), "Phiếu bài tập 1");
    await user.selectOptions(screen.getByLabelText("Loại"), "BAI_TAP");
    await user.selectOptions(await screen.findByLabelText("Chương"), "math-g5-decimals");
    await user.click(screen.getByRole("button", { name: "Tải lên" }));
    await waitFor(() =>
      expect(uploads).toEqual([
        { name: "phieu-1.docx", title: "Phiếu bài tập 1", kind: "BAI_TAP", chapterId: "math-g5-decimals" },
      ]),
    );
    expect(await screen.findByText(/Đã tải lên «Phiếu bài tập 1»/)).toBeInTheDocument();
  });

  it("shows the text of a document as the RAG reads it", async () => {
    renderApp("/teacher/documents/d1", libraryApi().api);
    expect(await screen.findByText(/Bài 8\. Số thập phân/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mở file gốc" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xóa" })).toBeInTheDocument();
  });

  it("shows a chapter node by node with the answers, hints and expected mistakes", async () => {
    renderApp("/teacher/lessons/math-g5-decimals", libraryApi().api);
    expect(await screen.findByRole("heading", { level: 2, name: "Phân số thập phân" })).toBeInTheDocument();
    const theory = screen.getByRole("region", { name: "Lý thuyết (các cách giảng)" });
    expect(theory).toHaveTextContent("Ví dụ trả lời đúng ý: 4/100 · 0,04");
    expect(theory).toHaveTextContent("Ý giải thích tham khảo: Tô 4 ô trong 100 ô");
    const items = screen.getByRole("region", { name: "Câu hỏi · Luyện tập" });
    expect(items).toHaveTextContent("Đáp án: 0,9");
    expect(items).toHaveTextContent("Lỗi sai dự đoán: 0,09 → Quên chữ số 0 giữ chỗ");
    expect(screen.getByText(/Bản nháp, chờ giáo viên duyệt/)).toBeInTheDocument();
  });

  it("lists the chapters, the geometry one still waiting for documents", async () => {
    renderApp("/teacher/lessons", libraryApi().api);
    expect(await screen.findByRole("link", { name: /Số thập phân/ })).toHaveTextContent("7 bài · 31 câu hỏi");
    expect(screen.getByText(/Diện tích hình tam giác, hình thang/)).toBeInTheDocument();
  });
});
