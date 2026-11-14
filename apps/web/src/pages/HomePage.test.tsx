import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderApp } from "../test/renderApp";

describe("the notebook landing page", () => {
  it("opens the student area in demo mode without sending visitors back to the landing page", async () => {
    const { user } = renderApp("/");
    await user.click(await screen.findByRole("button", { name: /Vào học cùng Buddy/ }));
    expect(await screen.findByRole("heading", { level: 1, name: /Chào/ })).toBeInTheDocument();
  });

  it("lets a keyboard reader explore lessons with expanded state and visible content", async () => {
    const { user } = renderApp("/");
    const lesson = await screen.findByRole("button", { name: /Diện tích hình tam giác/ });
    lesson.focus();
    await user.keyboard("{Enter}");
    expect(lesson).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Ghép hai tam giác bằng nhau, con tạo được hình gì?")).toBeVisible();
    expect(screen.getByRole("button", { name: /Làm quen với số thập phân/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("presents both subjects and marks English as a preview", async () => {
    renderApp("/");
    expect(await screen.findByRole("heading", { level: 3, name: "Toán lớp 5" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Tiếng Anh lớp 5" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Xem trước Tiếng Anh/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Bản xem trước").length).toBeGreaterThan(0);
  });

  it("switches the worked example between subjects", async () => {
    const { user } = renderApp("/");
    expect(await screen.findByText("Có 3 trong 10 phần được tô màu.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Tiếng Anh" }));
    expect(screen.getByRole("button", { name: "Tiếng Anh" })).toHaveAttribute("aria-pressed", "true");
    // English is Unit 11 "Family time" (D-T13, ENG-7a): the example is the unit's "Did you …?".
    expect(screen.getByText("Bạn hỏi “Did you swim?” và con đã bơi.")).toBeVisible();
  });

  it("changes the teaching step as the page scrolls through the sticky section, and a tab scrolls to its step", async () => {
    const { user } = renderApp("/");
    const loop = await screen.findByRole("group", { name: "Khám phá vòng học 6 bước" });
    const section = loop.closest("section") as HTMLElement;
    const stepOf = () =>
      within(loop)
        .getAllByRole("button")
        .findIndex((button) => button.getAttribute("aria-pressed") === "true");
    // jsdom has no layout: say how tall the section is and how far the page is scrolled into it.
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
    const scrolledInto = (pixels: number) => {
      section.getBoundingClientRect = () =>
        ({ top: -pixels, height: 2800, bottom: 2800 - pixels }) as DOMRect;
      fireEvent.scroll(window);
    };
    expect(stepOf()).toBe(0);

    scrolledInto(700); // 700 of 2800 (the sticky part is 0 high here): the second sixth
    await waitFor(() => expect(stepOf()).toBe(1));
    scrolledInto(1500); // past half: the fourth sixth
    await waitFor(() => expect(stepOf()).toBe(3));
    scrolledInto(2790); // the end
    await waitFor(() => expect(stepOf()).toBe(5));
    scrolledInto(0); // back to the top
    await waitFor(() => expect(stepOf()).toBe(0));

    // No auto-advance bar or pause button is left; a tab scrolls the page to the middle of its step.
    expect(screen.queryByRole("button", { name: /tự chạy/ })).not.toBeInTheDocument();
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    await user.click(within(loop).getByRole("button", { name: /Luyện tập/ }));
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: (2800 * 3.5) / 6 - 8 }));
    scrollTo.mockRestore();
  });

  it("shows direct contact links and scrolls the page back to the top", async () => {
    const { user } = renderApp("/");
    expect(screen.getByRole("link", { name: "ougvn.it2@gmail.com" })).toHaveAttribute(
      "href",
      "mailto:ougvn.it2@gmail.com",
    );
    expect(screen.getByRole("link", { name: "devhousesoftware.inc@gmail.com" })).toHaveAttribute(
      "href",
      "mailto:devhousesoftware.inc@gmail.com",
    );
    expect(screen.getByRole("link", { name: "0869 528 304" })).toHaveAttribute("href", "tel:+84869528304");

    Object.defineProperty(window, "scrollY", { configurable: true, value: 700 });
    fireEvent.scroll(window);
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    await user.click(screen.getByRole("button", { name: "Quay lại đầu trang" }));
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
    scrollTo.mockRestore();
    Object.defineProperty(window, "scrollY", { configurable: true, value: 0 });
  });
});
