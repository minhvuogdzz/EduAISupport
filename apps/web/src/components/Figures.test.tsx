import { QueryClient } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CurrentItem, FigureView, TeacherFigure } from "../api/contract";
import { AppProviders } from "../AppProviders";
import { QuestionCard } from "../features/student/QuestionCard";
import { FigureReview } from "../features/teacher/FigureReview";
import { testApi } from "../test/renderApp";
import { FiguresProvider } from "./Figures";
import { pullFigures, questionFigures, type FiguresValue } from "./figureModel";

const TAG = "[Hình: tam giác ABC]";
const F: FigureView = {
  figure_id: "f1",
  question_id: "Q-01",
  order: 1,
  tag: TAG,
  alt: "tam giác ABC",
  width: 300,
  height: 200,
  version: "one",
};
const ITEM: CurrentItem = {
  item_id: "Q-01a",
  item_attempt_id: "a1",
  stem: `Tính diện tích. ${TAG}`,
  answer_format: "open",
  options: [],
  expecting: "ANSWER",
  position: 1,
};

function fixture(teacher = false) {
  const api = testApi();
  let row: TeacherFigure = {
    ...F,
    chapter_id: "geometry",
    status: "REVIEW",
    method: "VECTOR",
    score: 0.5,
    page: 1,
    document_id: "d1",
    shown: false,
    decided_by: null,
  };
  api.figures = {
    list: vi.fn(() => Promise.resolve([F])),
    image: vi.fn(() => Promise.resolve(new Blob(["png"], { type: "image/png" }))),
    all: vi.fn(() => Promise.resolve([row])),
    decide: vi.fn((_id, action) => {
      row = {
        ...row,
        status: action === "approve" ? "APPROVED" : "REJECTED",
        shown: action === "approve",
        decided_by: "teacher",
      };
      return Promise.resolve(row);
    }),
    replace: vi.fn(() => Promise.resolve(row)),
  };
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui = render(
    <AppProviders api={api} queryClient={cache}>
      <FiguresProvider chapterId="geometry" who={teacher ? "teacher" : "student"}>
        {teacher ? <FigureReview chapterId="geometry" /> : <QuestionCard item={ITEM} total={1} />}
      </FiguresProvider>
    </AppProviders>,
  );
  return { api, ...ui, user: userEvent.setup() };
}

beforeEach(() => {
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:figure"), configurable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), configurable: true });
});
afterEach(() => {
  Reflect.deleteProperty(URL, "createObjectURL");
  Reflect.deleteProperty(URL, "revokeObjectURL");
});

describe("question figures", () => {
  it("does not guess from repeated descriptions; sub-questions keep their own image", () => {
    const other = { ...F, figure_id: "f2", question_id: "Q-02" };
    const value: FiguresValue = {
      who: "student",
      byTag: new Map([[TAG, [F, other]]]),
      byQuestion: new Map([
        ["Q-01", [F]],
        ["Q-02", [other]],
      ]),
    };
    expect(pullFigures(TAG, value).found).toEqual([]);
    expect(pullFigures(TAG, value, "Q-02b").found).toEqual([other]);
    expect(questionFigures(value, "Q-01b", "Phần b không lặp mô tả hình")).toEqual([F]);
    expect(questionFigures(value, "Q-01b", TAG)).toEqual([]);
  });

  it("shows authenticated image bytes on the child's question and preserves the words", async () => {
    const { api, container } = fixture();
    expect(await screen.findByAltText("tam giác ABC")).toHaveAttribute("src", "blob:figure");
    expect(container).toHaveTextContent("Tính diện tích.");
    expect(container.textContent).not.toContain("[Hình:");
    expect(api.figures!.image).toHaveBeenCalledWith("f1", "one", "student");
  });

  it("keeps an accessible description and a working retry if the image fails", async () => {
    const { api, user } = fixture();
    vi.mocked(api.figures!.image).mockRejectedValueOnce(new Error("network"));
    expect(await screen.findByText(/Chưa tải được hình/)).toHaveTextContent("tam giác ABC");
    await user.click(screen.getByRole("button", { name: "Tải lại hình" }));
    expect(await screen.findByAltText("tam giác ABC")).toBeInTheDocument();
  });

  it("lets the teacher approve, hide and replace a figure without touching plan decisions", async () => {
    const { api, user } = fixture(true);
    await user.click(await screen.findByText("Hình minh họa · 1 hình"));
    expect(screen.getByText(/Chưa hiện cho học sinh/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Duyệt hình Q-01" }));
    await waitFor(() => expect(screen.getByText(/Học sinh đang thấy/)).toBeInTheDocument());
    expect(api.figures!.decide).toHaveBeenCalledWith("f1", "approve");
    await user.click(screen.getByRole("button", { name: "Bỏ hình Q-01" }));
    await waitFor(() => expect(screen.getByText(/Chưa hiện cho học sinh/)).toBeInTheDocument());
    const file = new File(["png"], "new.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("Thay hình Q-01"), file);
    await waitFor(() =>
      expect(api.figures!.replace).toHaveBeenCalledWith(file, {
        chapterId: "geometry",
        questionId: "Q-01",
        order: 1,
        tag: TAG,
      }),
    );
    expect(api.figures!.image).toHaveBeenCalledWith("f1", "one", "teacher");
  });
});
