import { useState } from "react";
import { Mascot } from "../components/Mascot";
import { BookIcon, ChartIcon, UsersIcon } from "../components/icons";

const LOOP = [
  [
    "Ôn bài nền",
    "Bắt đầu từ điều con đã biết.",
    "Một câu ôn nhỏ giúp Buddy nhận ra phần kiến thức nền cần nhắc lại.",
  ],
  [
    "Giảng bài",
    "Hiểu vì sao, trước khi ghi nhớ.",
    "Lý thuyết được giải thích qua những hình ảnh và ví dụ gần gũi.",
  ],
  [
    "Kiểm tra hiểu",
    "Con thử nói theo cách của mình.",
    "Một câu hỏi ngắn hoặc một lời giải thích để nhìn rõ điều con vừa hiểu và điều còn đang vướng.",
  ],
  [
    "Học cách làm",
    "Cùng nhìn một cách làm.",
    "Con khám phá phương pháp và xem ví dụ từng bước, với lý do cho cách làm đó.",
  ],
  [
    "Luyện tập",
    "Đến lượt con tự thử sức.",
    "Con thực hành, nhận gợi ý theo mức cần thiết và quay lại tự làm.",
  ],
  [
    "Vận dụng",
    "Mang điều đã hiểu sang bài mới.",
    "Một tình huống khác giúp kiểm tra khả năng vận dụng kiến thức.",
  ],
  [
    "Qua bài",
    "Đi tiếp khi đã có đủ bằng chứng.",
    "Hệ thống đối chiếu các điều kiện qua bài, lưu tiến bộ và chọn bước học tiếp theo.",
  ],
];
export function CorePromise() {
  return (
    <section className="core-promise" aria-label="Giá trị cốt lõi Monkey Edu">
      <p className="eyebrow">HỌC ĐỂ HIỂU. CÓ NGƯỜI ĐỒNG HÀNH.</p>
      <div>
        {[
          ["01", "Con tự tìm ra cách làm", "Gia sư gợi mở, từng bước một."],
          ["02", "Tiến bộ có bằng chứng", "Nhìn cả cách nghĩ, không chỉ đáp án."],
          ["03", "Thầy cô giữ định hướng", "Nội dung được quản lý và có bước duyệt."],
        ].map(([id, title, text]) => (
          <article data-reveal key={id}>
            <span>{id}</span>
            <div>
              <h2>{title}</h2>
              <p>{text}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
export function LearningExperience() {
  const [parts, setParts] = useState(3);
  const [step, setStep] = useState(0);
  return (
    <>
      <section className="lesson-lab" id="try-math">
        <div data-reveal>
          <p className="eyebrow">CHẠM MỘT CHÚT. HIỂU THÊM MỘT CHÚT.</p>
          <h2>
            Đổi một chữ số.
            <br />
            <em>Thấy ngay ý nghĩa.</em>
          </h2>
          <p>
            Toán không chỉ nằm trên dòng chữ. Kéo thanh bên cạnh và nhìn số thập phân thành một phần của cả
            chiếc bánh.
          </p>
          <span className="lab-caption">Minh họa tương tác · Không phải bài kiểm tra</span>
        </div>
        <div className="lab-notebook" data-reveal>
          <div className="lab-paper-top">
            <span>SỔ KHÁM PHÁ CỦA CON</span>
            <BookIcon aria-hidden="true" />
          </div>
          <div className="lab-grid" aria-label={`${parts} trong 10 phần được tô màu`}>
            {Array.from({ length: 10 }, (_, i) => (
              <span key={i} className={i < parts ? "is-filled" : ""} />
            ))}
          </div>
          <div className="lab-equation">
            <span>
              <sup>{parts}</sup>
              <sub>10</sub>
            </span>
            <span>=</span>
            <strong>0,{parts}</strong>
            <Mascot size={82} mood="encouraging" />
          </div>
          <label htmlFor="fraction-parts">
            Tô màu <output htmlFor="fraction-parts">{parts}</output> trong 10 phần
          </label>
          <input
            id="fraction-parts"
            type="range"
            min="1"
            max="9"
            value={parts}
            onChange={(event) => setParts(Number(event.target.value))}
            aria-valuetext={`${parts} phần mười, bằng 0 phẩy ${parts}`}
          />
          <div className="lab-range-labels">
            <span>1 phần mười</span>
            <span>9 phần mười</span>
          </div>
        </div>
      </section>
      <section className="learning-loop-section" id="journey">
        <div className="section-intro" data-reveal>
          <p className="eyebrow">MỘT BUỔI HỌC CÓ ĐỊNH HƯỚNG</p>
          <h2>
            Không chỉ hỏi đáp.
            <br />
            <em>Có cả một cách dạy.</em>
          </h2>
          <p>
            Khám phá vòng học 7 bước. Mỗi bước có một mục đích; khi con còn vướng, gia sư có thể quay lại phần
            cần củng cố.
          </p>
        </div>
        <div
          className="learning-loop-controls"
          role="group"
          aria-label="Khám phá vòng học 7 bước"
          data-reveal
        >
          {LOOP.map(([label], i) => (
            <button key={label} aria-pressed={step === i} onClick={() => setStep(i)}>
              <span>0{i + 1}</span>
              <strong>{label}</strong>
            </button>
          ))}
        </div>
        <div className="learning-loop-panel" data-reveal>
          <div className="loop-orbit" aria-hidden="true">
            <svg viewBox="0 0 250 220">
              <ellipse
                cx="125"
                cy="110"
                rx="110"
                ry="82"
                fill="none"
                stroke="#bdd4dd"
                strokeDasharray="4 7"
              />
              {LOOP.map((_, i) => {
                const angle = (i / 7) * Math.PI * 2 - Math.PI / 2;
                return (
                  <circle
                    key={i}
                    cx={125 + 110 * Math.cos(angle)}
                    cy={110 + 82 * Math.sin(angle)}
                    r={step === i ? 8 : 4}
                    fill={step === i ? "#6099c5" : "#5d737e"}
                  />
                );
              })}
            </svg>
            <Mascot
              size={145}
              mood={
                step === 6
                  ? "celebrating"
                  : step === 3
                    ? "listening"
                    : step === 2
                      ? "thinking"
                      : "encouraging"
              }
            />
          </div>
          <div key={step} className="loop-copy">
            <p className="eyebrow">
              BƯỚC 0{step + 1} · {LOOP[step][0]}
            </p>
            <h3>{LOOP[step][1]}</h3>
            <p>{LOOP[step][2]}</p>
            <button className="text-link" onClick={() => setStep((step + 1) % LOOP.length)}>
              Khám phá bước tiếp <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </section>
      <section className="learning-connection" data-reveal>
        <div>
          <p className="eyebrow">TỪ MỘT GÓC HỌC, KẾT NỐI CẢ HÀNH TRÌNH</p>
          <h2>
            Con học từng bước.
            <br />
            <em>Mọi người cùng hiểu.</em>
          </h2>
          <p>
            Mỗi lượt trả lời góp thêm bằng chứng về việc học. Con nhìn điều mình đã làm được; người lớn có góc
            nhìn phù hợp để cùng con đi tiếp.
          </p>
        </div>
        <div className="connection-flow">
          <article>
            <BookIcon />
            <strong>Con khám phá</strong>
            <span>Thử, giải thích và luyện tập.</span>
          </article>
          <span className="connection-thread" aria-hidden="true" />
          <article>
            <UsersIcon />
            <strong>Bố mẹ đồng hành</strong>
            <span>Hiểu nhịp học và phần cần giúp.</span>
          </article>
          <span className="connection-thread" aria-hidden="true" />
          <article>
            <ChartIcon />
            <strong>Thầy cô định hướng</strong>
            <span>Xem bằng chứng, chọn cách hỗ trợ.</span>
          </article>
        </div>
      </section>
    </>
  );
}
