import type { CSSProperties } from "react";
import { useSearchParams } from "react-router";

import type { StudentOverview } from "../../api/contract";
import { BookIcon, StarIcon, TargetIcon } from "../../components/icons";
import { TEACHING_STEPS } from "../../components/labels";
import "./subjects.css";

const DOODLES = ["Hi!", "did", "We…", "?", "went", "★"];
const STEP_TONES = ["tone-sky", "tone-grape", "tone-coral", "tone-sun", "tone-leaf", "tone-rose"];

/** Floating English words behind the student's greeting: decoration only. */
export function EnglishDoodles() {
  return (
    <span className="en-doodles" aria-hidden="true">
      {DOODLES.map((doodle, index) => (
        <i key={doodle} lang="en" style={{ "--i": index } as CSSProperties}>
          {doodle}
        </i>
      ))}
    </span>
  );
}

/**
 * The units of English the tutor teaches (D-T13: one unit now). The pick lives in `?chapter=` as the
 * chapter picker of math does; a single unit is still shown, so the child sees what is being revised.
 */
export function UnitCards({ overview }: { overview: StudentOverview }) {
  const [params, setParams] = useSearchParams();
  const selected = params.get("chapter") ?? overview.chapter.chapter_id;
  const units = overview.chapters.length ? overview.chapters : [overview.chapter];
  return (
    <nav aria-label="Chọn unit" className="en-unit-cards">
      {units.map((unit, index) => {
        const current = unit.chapter_id === selected;
        const [number, ...rest] = unit.title.split(":");
        return (
          <button
            key={unit.chapter_id}
            type="button"
            aria-pressed={current}
            style={{ "--i": index } as CSSProperties}
            className={`en-unit-card tone-coral ${current ? "is-current" : ""}`}
            onClick={() => {
              const next = new URLSearchParams(params);
              next.set("chapter", unit.chapter_id);
              setParams(next, { replace: true });
            }}
          >
            <span className="en-badge">
              <BookIcon />
            </span>
            <span className="en-unit-card-text">
              <small>{number.trim()} · Tiếng Anh 5 Global Success</small>
              <strong lang="en">{rest.join(":").trim() || unit.title}</strong>
            </span>
            {current && <span className="en-unit-card-mark">Đang ôn</span>}
          </button>
        );
      })}
    </nav>
  );
}

/**
 * The six steps of the teaching cycle (ADR-059) on the part being revised, and the next goal (DI-113):
 * the same loop as math, said for an English lesson. Never a score.
 */
export function EnglishLoop({ overview }: { overview: StudentOverview }) {
  const current = overview.nodes.find((n) => n.status === "CURRENT") ?? overview.nodes.find((n) => !n.passed);
  const step = overview.current_step ?? null;
  return (
    <section aria-labelledby="loop-title" className="en-loop card">
      <div className="en-loop-head">
        <h2 id="loop-title" className="text-xl font-bold">
          Vòng ôn bài 6 bước
        </h2>
        {current && (
          <p className="en-goal">
            <TargetIcon aria-hidden="true" />
            <span>
              <small>Mục tiêu tiếp theo</small>
              <strong>{current.name}</strong>
              {current.pattern && !current.name.includes(current.pattern) && (
                <em lang="en">{current.pattern}</em>
              )}
            </span>
          </p>
        )}
      </div>
      <ol className="en-steps" aria-label={current ? `Các bước ôn ${current.name}` : "Các bước ôn"}>
        {TEACHING_STEPS.map((label, index) => {
          const number = index + 1;
          const done = step !== null && number < step;
          const now = number === step;
          return (
            <li
              key={label}
              aria-current={now ? "step" : undefined}
              style={{ "--i": index } as CSSProperties}
              className={`${STEP_TONES[index]} ${done ? "is-done" : ""} ${now ? "is-now" : ""}`}
            >
              <span className="en-step-dot" aria-hidden="true">
                {done ? "✓" : number}
              </span>
              <span>{label}</span>
              {done && <span className="sr-only"> (đã qua)</span>}
              {now && <span className="en-step-now">Con đang ở đây</span>}
            </li>
          );
        })}
      </ol>
      <p className="en-loop-note">
        <StarIcon aria-hidden="true" /> Cô giảng bằng tiếng Việt, con nói câu tiếng Anh. Bấm “Nói chuyện với
        cô” trong buổi học để trả lời bằng giọng nói.
      </p>
    </section>
  );
}

/**
 * For the parent (DI-113): three plain groups instead of a score: what the child has firmly, what to
 * practise, and the next goal, each part said with its target sentence (ADR-060 §8).
 */
export function ParentStatus({ overview }: { overview: StudentOverview }) {
  const firm = overview.nodes.filter((n) => n.quality === "INDEPENDENT" || n.quality === "SOLID");
  const practise = overview.nodes.filter((n) => n.quality === "FAMILIAR" || n.quality === "WITH_SUPPORT");
  const next = overview.nodes.find((n) => n.status === "CURRENT") ?? overview.nodes.find((n) => !n.passed);
  const groups = [
    {
      key: "firm",
      title: "Đã nắm chắc",
      tone: "tone-leaf",
      icon: <StarIcon />,
      nodes: firm,
      empty: "Chưa có phần nào.",
    },
    {
      key: "practise",
      title: "Cần luyện thêm",
      tone: "tone-sun",
      icon: <BookIcon />,
      nodes: practise,
      empty: "Chưa có phần nào cần ôn.",
    },
    {
      key: "next",
      title: "Mục tiêu tiếp theo",
      tone: "tone-grape",
      icon: <TargetIcon />,
      nodes: next ? [next] : [],
      empty: "Con đã ôn xong unit này.",
    },
  ];
  return (
    <section aria-label="Tình hình Tiếng Anh của con" className="en-status">
      {groups.map((g, index) => (
        <div key={g.key} className={`en-status-card ${g.tone}`} style={{ "--i": index } as CSSProperties}>
          <h2 className="en-status-title">
            <span className="en-badge">{g.icon}</span>
            {g.title}
          </h2>
          {g.nodes.length === 0 ? (
            <p className="text-sm">{g.empty}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {g.nodes.map((n) => (
                <li key={n.node_id}>
                  <span className="block font-semibold">{n.name}</span>
                  {n.pattern && !n.name.includes(n.pattern) && (
                    <span lang="en" className="en-pattern">
                      {n.pattern}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </section>
  );
}
