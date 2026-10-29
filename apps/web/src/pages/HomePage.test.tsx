import { fireEvent, screen } from "@testing-library/react";
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
