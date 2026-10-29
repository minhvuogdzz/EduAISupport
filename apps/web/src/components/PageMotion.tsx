import { useEffect, useRef, type ReactNode } from "react";

/** Progressive enhancement: content stays readable without observers or with reduced motion. */
export function PageMotion({ children, pageKey }: { children: ReactNode; pageKey: string }) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const frame = root.current;
    if (
      !frame ||
      !window.IntersectionObserver ||
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    )
      return;
    const observed = new Set<Element>();
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.setAttribute("data-visible", "true");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08 },
    );
    const observeContent = () => {
      frame.querySelectorAll("[data-reveal], .workspace-page section, [data-chart]").forEach((target) => {
        if (observed.has(target)) return;
        observed.add(target);
        target.setAttribute("data-motion", target.hasAttribute("data-chart") ? "chart" : "reveal");
        observer.observe(target);
      });
    };
    observeContent();
    // Dashboards arrive after their queries; animate those sections too.
    const additions = new MutationObserver(observeContent);
    additions.observe(frame, { childList: true, subtree: true });
    let raf = 0;
    const update = () => {
      raf = 0;
      const range = document.documentElement.scrollHeight - window.innerHeight;
      frame.style.setProperty("--scroll-progress", String(range > 0 ? window.scrollY / range : 0));
      frame.style.setProperty("--hero-shift", `${Math.min(window.scrollY * 0.12, 65)}px`);
    };
    const onScroll = () => {
      if (!raf) raf = window.requestAnimationFrame(update);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    update();
    return () => {
      observer.disconnect();
      additions.disconnect();
      window.removeEventListener("scroll", onScroll);
      window.cancelAnimationFrame(raf);
      observed.forEach((target) => target.removeAttribute("data-motion"));
    };
  }, [pageKey]);
  return (
    <div ref={root} className="page-motion">
      {children}
    </div>
  );
}
