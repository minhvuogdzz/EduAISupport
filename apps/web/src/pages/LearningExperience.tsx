import { useEffect, useRef, useState, type CSSProperties } from "react";

import { Burst } from "../components/Burst";
import { CalculatorIcon, GlobeIcon, StarIcon } from "../components/icons";
import { Mascot, type Mood } from "../components/Mascot";
import "./home.css";
import { Wave } from "./Wave";

type Subject = "math" | "english";

const STEPS: { title: string; text: string; caption: string; mood: Mood }[] = [
  {
    title: "Bắt đầu từ điều con nhìn thấy.",
    text: "Một hình vẽ, một tình huống quen thuộc để con có chỗ dựa khi suy nghĩ.",
    caption: "Nhìn một chút",
    mood: "happy",
  },
  {
    title: "Một câu hỏi. Một lần tự nghĩ.",
    text: "Buddy gợi mở và lắng nghe cách con giải thích. Còn vướng thì mình thử cách khác.",
    caption: "Thử nghĩ xem",
    mood: "thinking",
  },
  {
    title: "Hiểu rồi, con nói lại thử nhé.",
    text: "Con tự nói được cách làm, Buddy nhận ra chỗ cần ôn và chọn bước tiếp theo.",
    caption: "Nói theo cách của con",
    mood: "encouraging",
  },
];

const EXAMPLES: Record<Subject, { question: string; answer: string; lang?: string }[]> = {
  math: [
    { question: "Có 3 trong 10 phần được tô màu.", answer: "Ba phần mười" },
    { question: "Ba phần mười viết bằng số thập phân thế nào?", answer: "3/10 = 0,3" },
    { question: "Vì sao 0,3 bằng ba phần mười?", answer: "Vì 3 ở hàng phần mười!" },
  ],
  english: [
    { question: "Bạn hỏi “Did you swim?” và con đã bơi.", answer: "Yes, I did.", lang: "en" },
    { question: "“What did your family do in Nha Trang?”", answer: "We ate seafood.", lang: "en" },
    { question: "Vì sao trả lời bằng “did”?", answer: "Vì bạn hỏi bằng “did”!" },
  ],
};

const WORDS = [
  { word: "collect seashells", meaning: "nhặt vỏ sò" },
  { word: "eat seafood", meaning: "ăn hải sản" },
  { word: "buy souvenirs", meaning: "mua quà lưu niệm" },
  { word: "take photos", meaning: "chụp ảnh" },
];

const LOOP = [
  [
    "Ôn và giảng bài nền",
    "Nhắc lại điều con biết, rồi hiểu vì sao.",
    "Một câu ôn nhỏ giúp Buddy nhận ra phần nền cần nhắc lại, rồi lý thuyết được giải thích qua hình ảnh và ví dụ gần gũi.",
  ],
  [
    "Kiểm tra hiểu",
    "Con thử nói theo cách của mình.",
    "Một câu hỏi ngắn để nhìn rõ điều con vừa hiểu và điều còn vướng.",
  ],
  ["Học cách làm", "Cùng nhìn một cách làm.", "Con xem ví dụ từng bước, với lý do cho cách làm đó."],
  ["Luyện tập", "Đến lượt con tự thử sức.", "Con thực hành, nhận gợi ý vừa đủ và quay lại tự làm."],
  ["Vận dụng", "Mang điều đã hiểu sang bài mới.", "Một tình huống khác để thử khả năng vận dụng."],
  ["Qua bài", "Đi tiếp khi đã có đủ bằng chứng.", "Hệ thống đối chiếu điều kiện qua bài và lưu tiến bộ."],
];

function loopMood(step: number): Mood {
  if (step === 5) return "celebrating";
  if (step === 2) return "listening";
  return step === 1 ? "thinking" : "encouraging";
}

function TenGrid({ parts }: { parts: number }) {
  return (
    <div className="hm-ten" role="img" aria-label={`${parts} trong 10 phần được tô màu`}>
      {Array.from({ length: 10 }, (_, i) => (
        <span key={i} className={i < parts ? "is-on" : ""} style={{ "--i": i } as CSSProperties} />
      ))}
    </div>
  );
}

/** The worked example of how a lesson goes; one way of learning, shown in either subject. */
function LearningStory() {
  const [subject, setSubject] = useState<Subject>("math");
  const [step, setStep] = useState(0);
  const example = EXAMPLES[subject][step];
  return (
    <section id="learning" className="hm-section">
      <div className="hm-intro" data-reveal>
        <p className="hm-kicker">Cách mình học</p>
        <h2>
          Từ “con chưa biết” <mark>đến “con làm được”.</mark>
        </h2>
      </div>
      <div className="hm-toggle" role="group" aria-label="Xem ví dụ theo môn" data-reveal>
        <button aria-pressed={subject === "math"} onClick={() => setSubject("math")}>
          <CalculatorIcon /> Toán
        </button>
        <button aria-pressed={subject === "english"} onClick={() => setSubject("english")}>
          <GlobeIcon /> Tiếng Anh
        </button>
      </div>
      <div className="hm-story" data-reveal>
        <div className="hm-story-steps" role="group" aria-label="Các bước minh họa">
          {STEPS.map((item, i) => (
            <button key={item.caption} aria-pressed={step === i} onClick={() => setStep(i)}>
              <span className="hm-index">{i + 1}</span>
              <span>
                <strong>{item.title}</strong>
                <small>{item.text}</small>
              </span>
            </button>
          ))}
        </div>
        <div className={`hm-story-card is-${subject}`} key={`${subject}-${step}`}>
          <p className="hm-story-caption">{STEPS[step].caption}</p>
          {subject === "math" ? (
            <TenGrid parts={3} />
          ) : (
            <div className="hm-chat-scene" aria-hidden="true">
              <span lang="en">Hello!</span>
              <span lang="en">Hi!</span>
            </div>
          )}
          <p className="hm-story-question">{example.question}</p>
          <p className="hm-story-answer" lang={example.lang}>
            {example.answer}
          </p>
          <Mascot size={92} mood={STEPS[step].mood} animated />
          <small className="hm-note">Minh họa cách học, không phải buổi học thật</small>
        </div>
      </div>
    </section>
  );
}

function WordFlip({ word, meaning }: { word: string; meaning: string }) {
  const [open, setOpen] = useState(false);
  const [fire, setFire] = useState(0);
  return (
    <button
      type="button"
      className={`flip-card tone-coral ${open ? "is-open" : ""}`}
      aria-pressed={open}
      onClick={() => {
        setOpen(!open);
        if (!open) setFire((value) => value + 1);
      }}
    >
      <span className="flip-inner">
        <span className="flip-face">
          <strong lang="en">{word}</strong>
          <small>Chạm để lật</small>
        </span>
        <span className="flip-face flip-back">
          <strong>{meaning}</strong>
        </span>
      </span>
      <Burst fire={fire} />
    </button>
  );
}

/** Two small things to touch: a slider for decimals and word cards for English. Neither is graded. */
function TryIt() {
  const [parts, setParts] = useState(3);
  return (
    <section id="try" className="hm-band">
      <Wave colour="#fff6df" flip />
      <div className="hm-section">
        <div className="hm-intro" data-reveal>
          <p className="hm-kicker">Chạm một chút, hiểu thêm một chút</p>
          <h2>
            Thử ngay <mark>ở đây.</mark>
          </h2>
          <p>Minh họa tương tác, không phải bài kiểm tra.</p>
        </div>
        <div className="hm-labs">
          <div className="hm-lab subject-tile-math" data-reveal>
            <h3>Toán: kéo để tô màu</h3>
            <TenGrid parts={parts} />
            <p className="hm-lab-result" key={parts}>
              {parts}/10 = <strong>0,{parts}</strong>
            </p>
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
          </div>
          <div className="hm-lab subject-tile-english" data-reveal>
            <h3>Tiếng Anh: chạm để lật thẻ</h3>
            <div className="hm-word-grid">
              {WORDS.map((item) => (
                <WordFlip key={item.word} word={item.word} meaning={item.meaning} />
              ))}
            </div>
          </div>
        </div>
      </div>
      <Wave colour="#fff6df" />
    </section>
  );
}

/** Scrolling distance that one step of the loop takes, as a share of the screen height. */
const STEP_SCROLL_VH = 0.55;

/**
 * The six-step teaching loop, which today runs in maths; English will follow it once it is taught.
 *
 * Sticky scroll: the section is tall and its content sticks under the header, and the step follows how far
 * the page is scrolled through it (CSS class `hm-scrolly`). A chip scrolls to its step. On a short screen the
 * content does not fit under the header, so the section is plain and a chip sets the step directly.
 */
function TeachingLoop() {
  const [step, setStep] = useState(0);
  const wrap = useRef<HTMLElement>(null);
  const stick = useRef<HTMLDivElement>(null);

  const shortScreen = () => window.matchMedia?.("(max-height: 680px)").matches ?? false;

  // The header is sticky too: the content sticks right under it, whatever its height is on this screen.
  useEffect(() => {
    const place = () => {
      const header = document.querySelector(".site-header");
      const top = (header?.getBoundingClientRect().height ?? 0) + 8;
      wrap.current?.style.setProperty("--stick-top", `${Math.round(top)}px`);
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, []);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const section = wrap.current;
      if (!section || shortScreen()) return;
      const top = parseFloat(section.style.getPropertyValue("--stick-top")) || 0;
      const span = section.getBoundingClientRect().height - (stick.current?.offsetHeight ?? 0);
      if (span <= 0) return;
      const progress = Math.min(0.9999, Math.max(0, (top - section.getBoundingClientRect().top) / span));
      setStep(Math.floor(progress * LOOP.length));
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      window.cancelAnimationFrame(frame);
    };
  }, []);

  const goTo = (index: number) => {
    const section = wrap.current;
    if (!section || shortScreen()) {
      setStep(index);
      return;
    }
    const top = parseFloat(section.style.getPropertyValue("--stick-top")) || 0;
    const span = section.getBoundingClientRect().height - (stick.current?.offsetHeight ?? 0);
    const start = section.getBoundingClientRect().top + window.scrollY - top;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    // The middle of the band of that step, so rounding never lands on its neighbour.
    window.scrollTo({
      top: start + (span * (index + 0.5)) / LOOP.length,
      behavior: reduced ? "auto" : "smooth",
    });
    setStep(index);
  };

  return (
    <section
      id="journey"
      className="hm-dark hm-scrolly"
      ref={wrap}
      style={{ "--step-vh": `${STEP_SCROLL_VH * 100}vh`, "--steps": LOOP.length } as CSSProperties}
    >
      <Wave colour="#23506e" flip />
      <div className="hm-scrolly-stick" ref={stick}>
        <span className="hm-stars" aria-hidden="true">
          {Array.from({ length: 9 }, (_, i) => (
            <StarIcon key={i} style={{ "--i": i } as CSSProperties} />
          ))}
        </span>
        <div className="hm-section">
          <div className="hm-intro">
            <p className="hm-kicker">Một buổi học có định hướng</p>
            <h2>Không chỉ hỏi đáp, có cả một cách dạy.</h2>
            <p>Mỗi bước có một mục đích; khi con còn vướng, gia sư quay lại phần cần củng cố.</p>
          </div>
          <div className="hm-loop-steps" role="group" aria-label="Khám phá vòng học 6 bước">
            {LOOP.map(([label], i) => (
              <button
                key={label}
                aria-pressed={step === i}
                className={i < step ? "is-done" : ""}
                onClick={() => goTo(i)}
              >
                <span>{i + 1}</span>
                {label}
              </button>
            ))}
          </div>
          <div className="hm-loop-panel">
            <span className="hm-hop" key={step}>
              <Mascot size={150} mood={loopMood(step)} animated />
            </span>
            <div key={`copy-${step}`} className="hm-loop-copy">
              <p className="hm-loop-count">
                Bước {step + 1} · {LOOP[step][0]}
              </p>
              <h3>{LOOP[step][1]}</h3>
              <p>{LOOP[step][2]}</p>
            </div>
          </div>
          <p className="hm-loop-note">
            Cuộn xuống để sang bước tiếp theo. Vòng 6 bước đang chạy ở môn Toán; Tiếng Anh sẽ theo cùng cách
            dạy khi hoàn thiện.
          </p>
        </div>
      </div>
      <Wave colour="#23506e" />
    </section>
  );
}

export function LearningExperience() {
  return (
    <>
      <LearningStory />
      <TryIt />
      <TeachingLoop />
    </>
  );
}
