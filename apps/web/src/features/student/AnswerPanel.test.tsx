import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { CommandType, CurrentItem, MicroChoice } from "../../api/contract";
import { AnswerPanel } from "./AnswerPanel";

const compareItem: CurrentItem = {
  item_attempt_id: "a1",
  item_id: "GP-01",
  stem: "Điền dấu >, < hoặc = vào chỗ chấm: 0,25 … 0,3",
  answer_format: "compare",
  options: [],
  expecting: "ANSWER",
  position: 3,
};

function setup(
  overrides: Partial<{
    item: CurrentItem;
    allowed: CommandType[];
    busy: boolean;
    pendingChoice: MicroChoice[] | null;
    submitResult: boolean;
  }> = {},
) {
  const onSubmit = vi.fn(() => Promise.resolve(overrides.submitResult ?? true));
  const onHint = vi.fn();
  const onChoose = vi.fn();
  render(
    <AnswerPanel
      item={overrides.item ?? compareItem}
      pendingChoice={overrides.pendingChoice ?? null}
      allowed={overrides.allowed ?? ["ANSWER", "HINT_REQUEST"]}
      busy={overrides.busy ?? false}
      onSubmit={onSubmit}
      onHint={onHint}
      onChoose={onChoose}
    />,
  );
  return { onSubmit, onHint, onChoose, user: userEvent.setup(), box: screen.getByRole("textbox") };
}

describe("AnswerPanel", () => {
  it("inserts signs at the cursor, so '0,25 < 0,3' can be built without a keyboard", async () => {
    const { user, box } = setup();
    await user.type(box, "0,25  0,3");
    (box as HTMLTextAreaElement).setSelectionRange(5, 5);
    await user.click(screen.getByRole("button", { name: "dấu bé hơn" }));
    expect(box).toHaveValue("0,25 < 0,3");
  });

  it("sends with Enter and the Gửi button, and clears the box once sent", async () => {
    const { user, box, onSubmit } = setup();
    await user.type(box, "0,25 < 0,3{Enter}");
    expect(onSubmit).toHaveBeenCalledWith("0,25 < 0,3");
    expect(box).toHaveValue("");
    await user.type(box, "<");
    await user.click(screen.getByRole("button", { name: "Gửi" }));
    expect(onSubmit).toHaveBeenLastCalledWith("<");
  });

  it("keeps Shift+Enter as a new line and ignores Enter while an IME composes a letter", async () => {
    const { user, box, onSubmit } = setup();
    await user.type(box, "vì{Shift>}{Enter}{/Shift}2 < 3");
    expect(box).toHaveValue("vì\n2 < 3");
    fireEvent.keyDown(box, { key: "Enter", isComposing: true });
    fireEvent.keyDown(box, { key: "Enter", keyCode: 229 });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("gives the text back when it could not be sent", async () => {
    const { user, box, onSubmit } = setup({ submitResult: false });
    await user.type(box, "0,25 > 0,3{Enter}");
    expect(onSubmit).toHaveBeenCalled();
    expect(box).toHaveValue("0,25 > 0,3");
  });

  it("offers the options of a choice item and Đúng/Sai for a boolean item as quick answers", async () => {
    const { user, box } = setup({
      item: {
        ...compareItem,
        answer_format: "choice",
        options: [
          { id: "A", text: "Lan" },
          { id: "B", text: "Hoa" },
        ],
      },
    });
    await user.click(screen.getByRole("button", { name: "Hoa" }));
    expect(box).toHaveValue("Hoa");
    expect(screen.queryByRole("button", { name: "dấu bé hơn" })).not.toBeInTheDocument();
  });

  it("hides quick answers while an explanation is expected", () => {
    setup({ item: { ...compareItem, answer_format: "boolean", expecting: "EXPLANATION" } });
    expect(screen.queryByRole("button", { name: "Đúng" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Lời giải thích của con")).toBeInTheDocument();
  });

  it("shows the tutor's micro choices and sends the chosen one", async () => {
    const choices = [
      { choice_id: "SMALL", label: "Gợi ý nhỏ" },
      { choice_id: "EXAMPLE", label: "Ví dụ tương tự" },
    ];
    const { user, onChoose } = setup({ pendingChoice: choices, allowed: ["ANSWER", "CHOICE"] });
    await user.click(screen.getByRole("button", { name: "Ví dụ tương tự" }));
    expect(onChoose).toHaveBeenCalledWith(choices[1]);
    expect(screen.getByRole("button", { name: /Xin gợi ý/ })).toBeDisabled();
  });

  it("locks sending while the tutor answers, but lets the student keep typing", async () => {
    const { user, box, onSubmit, onHint } = setup({ busy: true });
    await user.type(box, "<{Enter}");
    expect(box).toHaveValue("<");
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Gửi" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Xin gợi ý/ })).toBeDisabled();
    expect(screen.getByText("Cô đang trả lời…")).toBeInTheDocument();
    expect(onHint).not.toHaveBeenCalled();
  });
});
