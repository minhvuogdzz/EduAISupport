import { Link } from "react-router";

import { CalculatorIcon, GlobeIcon } from "../../components/icons";
import "./subjects.css";

/** The subjects of an area, as two tiles. Each role passes the two pages of its own area. */
export function SubjectSwitch({
  current,
  mathTo = "/student",
  englishTo = "/student/english",
}: {
  current: "math" | "english";
  mathTo?: string;
  englishTo?: string;
}) {
  return (
    <nav aria-label="Chọn môn học" className="subject-switch">
      <Link
        to={mathTo}
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
      </Link>
      <Link
        to={englishTo}
        aria-current={current === "english" ? "page" : undefined}
        className="subject-tile subject-tile-english"
      >
        <span className="subject-tile-icon">
          <GlobeIcon />
        </span>
        <span className="subject-tile-text">
          <strong>Tiếng Anh</strong>
          <small>Bản xem trước</small>
        </span>
      </Link>
    </nav>
  );
}
