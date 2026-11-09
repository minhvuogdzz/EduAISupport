import { useState } from "react";
import { Link } from "react-router";

import { ArrowRightIcon, CalculatorIcon, GlobeIcon } from "../components/icons";
import { ENGLISH_UNITS } from "../features/english/content";
import "../features/english/subjects.css";
import "./home.css";
import { Wave } from "./Wave";

const MATH_LESSONS = [
  {
    name: "Làm quen với số thập phân",
    note: "Từ một phần của chiếc bánh đến một cách viết mới.",
    sample: "Ba phần mười có thể viết là 0,3. Vậy bảy phần mười thì sao?",
  },
  {
    name: "So sánh & tính toán",
    note: "Hiểu giá trị mỗi hàng, rồi tự tìm ra quy tắc.",
    sample: "0,5 và 0,50 có chỉ cùng một lượng không? Con thử hình dung nhé.",
  },
  {
    name: "Diện tích hình tam giác",
    note: "Cắt, ghép và khám phá mối liên hệ giữa các hình.",
    sample: "Ghép hai tam giác bằng nhau, con tạo được hình gì?",
  },
  {
    name: "Diện tích hình thang",
    note: "Từ điều đã biết, tìm cách giải một thử thách mới.",
    sample: "Hai đáy và chiều cao giúp mình tìm diện tích như thế nào?",
  },
];

/** The two subjects, right under the hero. English says it is a preview, so nobody expects a tutor yet. */
export function SubjectsShowcase() {
  return (
    <section id="subjects" className="hm-section" aria-labelledby="subjects-title">
      <div className="hm-intro" data-reveal>
        <p className="hm-kicker">Các môn học</p>
        <h2 id="subjects-title">
          Một người bạn, <mark>nhiều môn học.</mark>
        </h2>
        <p>Cùng một cách học: hỏi để con nghĩ, gợi ý khi con cần và ghi nhận từng bước tiến.</p>
      </div>
      <div className="hm-subjects">
        <article className="hm-subject subject-tile-math" data-reveal>
          <header>
            <span className="subject-tile-icon">
              <CalculatorIcon />
            </span>
            <span className="hm-tag">Đang học được</span>
          </header>
          <h3>Toán lớp 5</h3>
          <p>Hiểu vì sao trước khi ghi nhớ, rồi tự làm và tự giải thích lại cách làm của mình.</p>
          <ul className="hm-subject-list">
            <li>Số thập phân</li>
            <li>Diện tích hình tam giác, hình thang</li>
          </ul>
          <Link to="/student" className="hm-subject-go">
            Vào học Toán <ArrowRightIcon />
          </Link>
        </article>
        <article className="hm-subject subject-tile-english" data-reveal>
          <header>
            <span className="subject-tile-icon">
              <GlobeIcon />
            </span>
            <span className="hm-tag">Bản xem trước</span>
          </header>
          <h3>Tiếng Anh lớp 5</h3>
          <p>Sáu chủ đề gần gũi với bốn kỹ năng nghe, nói, đọc, viết. Cô Buddy đang soạn bài.</p>
          <ul className="hm-subject-chips" lang="en">
            {ENGLISH_UNITS.map((unit) => (
              <li key={unit.id}>{unit.title}</li>
            ))}
          </ul>
          <Link to="/student/english" className="hm-subject-go">
            Xem trước Tiếng Anh <ArrowRightIcon />
          </Link>
        </article>
      </div>
    </section>
  );
}

/** What each subject covers: the maths lessons open one at a time; the English topics link to their previews. */
export function Curriculum({ onOpenStudent }: { onOpenStudent: () => void }) {
  const [lesson, setLesson] = useState(0);
  return (
    <section id="curriculum" className="hm-band">
      <Wave colour="#fff6df" flip />
      <div className="hm-section">
        <div className="hm-intro" data-reveal>
          <p className="hm-kicker">Những điều mình sẽ khám phá</p>
          <h2>
            Từ dấu phẩy nhỏ, <mark>đến lời chào đầu tiên.</mark>
          </h2>
        </div>
        <div className="hm-curriculum">
          <div data-reveal>
            <h3 className="hm-column-title">Toán</h3>
            <div className="hm-accordion">
              {MATH_LESSONS.map((item, i) => (
                <div className={lesson === i ? "is-open" : ""} key={item.name}>
                  <h4>
                    <button
                      aria-expanded={lesson === i}
                      aria-controls={`lesson-preview-${i}`}
                      onClick={() => setLesson(i)}
                    >
                      <span className="hm-index">{i + 1}</span>
                      <span>{item.name}</span>
                    </button>
                  </h4>
                  <div id={`lesson-preview-${i}`} hidden={lesson !== i}>
                    <p>{item.note}</p>
                    <blockquote>{item.sample}</blockquote>
                  </div>
                </div>
              ))}
            </div>
            <button className="hm-link" onClick={onOpenStudent}>
              Xem chương đang học của con <ArrowRightIcon />
            </button>
          </div>
          <div data-reveal>
            <h3 className="hm-column-title">
              Tiếng Anh <small>Bản xem trước</small>
            </h3>
            <ol className="hm-topics">
              {ENGLISH_UNITS.map((unit) => (
                <li key={unit.id} className={unit.tone}>
                  <Link to={`/student/english/${unit.id}`}>
                    <span className="en-badge">
                      <unit.icon />
                    </span>
                    <span>
                      <strong lang="en">{unit.title}</strong>
                      <small>{unit.subtitle}</small>
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
      <Wave colour="#fff6df" />
    </section>
  );
}
