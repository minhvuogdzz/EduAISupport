import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PageMotion } from "./PageMotion";

afterEach(() => vi.unstubAllGlobals());

describe("progressive page motion", () => {
  it("reveals sections that arrive after dashboard data, and releases observers on exit", async () => {
    let notify: IntersectionObserverCallback = () => {};
    const observe = vi.fn();
    const disconnect = vi.fn();
    vi.stubGlobal("matchMedia", () => ({ matches: false }));
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: IntersectionObserverCallback) {
          notify = callback;
        }
        observe = observe;
        unobserve = vi.fn();
        disconnect = disconnect;
      },
    );
    const { rerender, unmount } = render(
      <PageMotion pageKey="/teacher">
        <div className="workspace-page">Đang tải…</div>
      </PageMotion>,
    );
    rerender(
      <PageMotion pageKey="/teacher">
        <div className="workspace-page">
          <section aria-label="Dữ liệu lớp">
            Đã tải
            <svg data-chart role="img" aria-label="Tiến bộ học tập">
              <path className="chart-line" />
            </svg>
          </section>
        </div>
      </PageMotion>,
    );
    const section = screen.getByRole("region", { name: "Dữ liệu lớp" });
    const chart = screen.getByRole("img", { name: "Tiến bộ học tập" });
    await waitFor(() => expect(observe).toHaveBeenCalledWith(chart));
    expect(chart).toHaveAttribute("data-motion", "chart");
    expect(chart).not.toHaveAttribute("data-visible");
    await waitFor(() => expect(observe).toHaveBeenCalledWith(section));
    act(() =>
      notify(
        [
          {
            target: section,
            isIntersecting: true,
            intersectionRatio: 1,
            boundingClientRect: section.getBoundingClientRect(),
            intersectionRect: section.getBoundingClientRect(),
            rootBounds: null,
            time: 0,
          },
        ],
        {} as IntersectionObserver,
      ),
    );
    expect(section).toHaveAttribute("data-visible", "true");
    // A visible dashboard section must not start plots that are still below the fold.
    expect(chart).not.toHaveAttribute("data-visible");
    act(() =>
      notify(
        [
          {
            target: chart,
            isIntersecting: true,
            intersectionRatio: 1,
            boundingClientRect: chart.getBoundingClientRect(),
            intersectionRect: chart.getBoundingClientRect(),
            rootBounds: null,
            time: 0,
          },
        ],
        {} as IntersectionObserver,
      ),
    );
    expect(chart).toHaveAttribute("data-visible", "true");
    unmount();
    expect(disconnect).toHaveBeenCalledOnce();
  });

  it("keeps content visible without motion when the reader requests reduced motion", () => {
    const construct = vi.fn();
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
    vi.stubGlobal("IntersectionObserver", construct);
    render(
      <PageMotion pageKey="/">
        <section data-reveal>Kiến thức luôn đọc được</section>
        <svg data-chart role="img" aria-label="Biểu đồ không chuyển động" />
      </PageMotion>,
    );
    expect(screen.getByText("Kiến thức luôn đọc được")).not.toHaveAttribute("data-motion");
    expect(screen.getByRole("img", { name: "Biểu đồ không chuyển động" })).not.toHaveAttribute("data-motion");
    expect(construct).not.toHaveBeenCalled();
  });
});
