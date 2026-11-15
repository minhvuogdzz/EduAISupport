import { Link } from "react-router";

import { CalculatorIcon, GlobeIcon } from "../../components/icons";
import "./subjects.css";

/** A tile followed by hand: the parent's page then stays on that subject (ENG-7c). */
const PICKED = { picked: true } as const;

/**
 * The subjects of an area, as two tiles. Each role passes the two pages of its own area. `latest` marks the
 * subject the child studied last (ENG-7c, from the server's list of what the child studied).
 */
export function SubjectSwitch({
  current,
  mathTo = "/student",
  englishTo = "/student/english",
  latest,
}: {
  current: "math" | "english";
  mathTo?: string;
  englishTo?: string;
  latest?: "math" | "english" | null;
}) {
  return (
    <nav aria-label="Chọn môn học" className="subject-switch">
      <Link
        to={mathTo}
        state={PICKED}
        aria-current={current === "math" ? "page" : undefined}
        className="subject-tile subject-tile-math"
      >
        <span className="subject-tile-icon">
          <CalculatorIcon />
        </span>
        <span className="subject-tile-text">
          <strong>Toán</strong>
          <small>Đang học được</small>
        </span>
        {latest === "math" && <span className="subject-tile-latest">Vừa học</span>}
      </Link>
      <Link
        to={englishTo}
        state={PICKED}
        aria-current={current === "english" ? "page" : undefined}
        className="subject-tile subject-tile-english"
      >
        <span className="subject-tile-icon">
          <GlobeIcon />
        </span>
        <span className="subject-tile-text">
          <strong>Tiếng Anh</strong>
          <small>Unit 11 · Family time</small>
        </span>
        {latest === "english" && <span className="subject-tile-latest">Vừa học</span>}
      </Link>
    </nav>
  );
}
