import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { VoiceLive } from "./useVoiceLive";
import { sentences } from "./useVoiceLive";
import { VoiceBar } from "./VoiceBar";

function live(over: Partial<VoiceLive> = {}): VoiceLive {
  return {
    available: true,
    on: false,
    phase: "off",
    heard: "",
    level: 0,
    problem: null,
    toggle: vi.fn(),
    listenNow: vi.fn(),
    ...over,
  };
}

describe("voice live (ADR-030)", () => {
  it("reads a long message sentence by sentence, short ones together", () => {
    expect(sentences("Đúng rồi! Con giỏi lắm. Bây giờ mình sang bài mới nhé.")).toEqual([
      "Đúng rồi! Con giỏi lắm. Bây giờ mình sang bài mới nhé.",
    ]);
    const long = `${"Phần nguyên bằng nhau thì so sánh hàng phần mười. ".repeat(3)}Con thử nhé?`;
    const parts = sentences(long);
    expect(parts.length).toBeGreaterThan(1);
    expect(parts.every((p) => p.length <= 160)).toBe(true);
    expect(parts.join(" ")).toBe(long.trim());
  });

  it("offers to talk with the tutor, and hides when the browser cannot", () => {
    const voice = live();
    const { rerender } = render(<VoiceBar voice={voice} />);
    fireEvent.click(screen.getByRole("button", { name: "🎤 Nói chuyện với cô" }));
    expect(voice.toggle).toHaveBeenCalled();
    rerender(<VoiceBar voice={live({ available: false })} />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows what the tutor does and what it heard", () => {
    const { rerender } = render(<VoiceBar voice={live({ on: true, phase: "listening" })} />);
    expect(screen.getByText(/Cô đang nghe con nói/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dừng nghe" })).toBeInTheDocument();
    rerender(<VoiceBar voice={live({ on: true, phase: "waiting", heard: "ba phẩy năm" })} />);
    expect(screen.getByText("Cô nghe con nói: «ba phẩy năm»")).toBeInTheDocument();
    rerender(
      <VoiceBar voice={live({ on: true, phase: "waiting", problem: "Cô chưa nghe rõ, con nói lại nhé." })} />,
    );
    expect(screen.getByText("Cô chưa nghe rõ, con nói lại nhé.")).toBeInTheDocument();
  });
});
