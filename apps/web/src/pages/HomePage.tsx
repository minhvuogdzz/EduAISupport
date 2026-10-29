import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import type { AccountKind } from "../api/contract";
import { AppShell, PinDialog } from "../components/AppShell";
import { Mascot, type Mood } from "../components/Mascot";
import { homeOf, useAuth } from "../features/auth/authContext";
import { BuddyShowcase } from "./BuddyShowcase";
import { HeroBoard } from "./HeroBoard";
import { CorePromise, LearningExperience } from "./LearningExperience";
import { ProjectBenefits } from "./ProjectBenefits";

const LESSONS = [
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
const STEPS = [
  {
    title: "Bắt đầu từ điều con nhìn thấy.",
    text: "Một hình vẽ, một ví dụ quen thuộc. Kiến thức mới bắt đầu từ những điều gần gũi, để con có chỗ dựa khi suy nghĩ.",
    caption: "Nhìn một chút",
    question: "Có 3 trong 10 phần được tô màu.",
    answer: "Ba phần mười",
    mood: "happy" as Mood,
  },
  {
    title: "Một câu hỏi. Một lần tự nghĩ.",
    text: "Gia sư gợi mở từng bước và lắng nghe cách con giải thích. Khi con còn vướng, mình thử một cách diễn đạt khác.",
    caption: "Thử nghĩ xem",
    question: "Ba phần mười viết bằng số thập phân thế nào?",
    answer: "3/10 = 0,3",
    mood: "thinking" as Mood,
  },
  {
    title: "Hiểu rồi, con nói lại thử nhé.",
    text: "Điều quan trọng là con tự nói được cách làm. Mỗi câu trả lời giúp gia sư nhận ra chỗ cần ôn và chọn bước tiếp theo.",
    caption: "Nói theo cách của con",
    question: "Vì sao 0,3 bằng ba phần mười?",
    answer: "Vì 3 ở hàng phần mười!",
    mood: "encouraging" as Mood,
  },
];

export function HomePage() {
  const { user, accounts, switchTo, loggedIn, studentSignup } = useAuth();
  const navigate = useNavigate();
  const [askingRole, setAskingRole] = useState<AccountKind | null>(null);
  const [lesson, setLesson] = useState(0);
  const [step, setStep] = useState(0);
  const story = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!window.IntersectionObserver || !story.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setStep(Number((entry.target as HTMLElement).dataset.step));
        });
      },
      { rootMargin: "-25% 0px -35% 0px", threshold: 0 },
    );
    story.current.querySelectorAll("[data-step]").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
  const openRole = (role: AccountKind) => {
    if (!user) {
      void navigate(accounts.length === 0 && !studentSignup ? homeOf(role) : `/login?role=${role}`);
      return;
    }
    if (user.kind === role) {
      void navigate(homeOf(role));
      return;
    }
    if (switchTo(role)) {
      loggedIn();
      void navigate(homeOf(role));
      return;
    }
    setAskingRole(role);
  };
  return (
    <AppShell>
      <title>Monkey Edu · Mỗi ngày, hiểu thêm một chút</title>
      <div className="hero-banner">
        <section className="home-hero">
          <div className="hero-copy">
            <p className="eyebrow hero-enter">MỘT NGƯỜI BẠN HỌC TOÁN · LỚP 5</p>
            <h1 className="hero-enter">
              À, thì ra
              <br />
              Toán <em>là thế!</em>
            </h1>
            <p className="hero-description hero-enter">
              Từ “con chưa hiểu” đến “để con thử nhé”.
              <br className="hidden sm:block" /> Cùng Monkey Buddy tìm cách làm, từng câu hỏi nhỏ.
            </p>
            <div className="hero-actions hero-enter">
              <button className="ink-button" onClick={() => openRole("STUDENT")}>
                Vào học cùng Buddy <span aria-hidden="true">↗</span>
              </button>
              <a className="text-link" href="#learning">
                Khám phá cách học <span aria-hidden="true">↓</span>
              </a>
            </div>
            <div className="hero-footnote hero-enter">
              <span className="little-rule" />
              <p>
                Không vội đưa lời giải.
                <br />
                Dành chỗ cho con tự nghĩ.
              </p>
            </div>
          </div>
          <HeroBoard />
          <a href="#learning" className="scroll-cue">
            <span aria-hidden="true">↓</span> Cuộn để cùng khám phá
          </a>
        </section>
      </div>

      <div className="chapter-ribbon" aria-hidden="true">
        <span>Cứ tò mò.</span>
        <i />
        <span>Cứ thử.</span>
        <i />
        <span>Cứ hỏi.</span>
        <i />
        <span>Mình cùng hiểu.</span>
      </div>

      <CorePromise />

      <section id="learning" className="learning-section">
        <div className="section-intro" data-reveal>
          <p className="eyebrow">CÁCH MÌNH HỌC</p>
          <h2>
            Từ “con chưa biết”
            <br />
            <em>đến “con làm được”.</em>
          </h2>
          <p>
            Không cần hiểu ngay từ đầu.
            <br />
            Mình cứ đi từng bước, cùng nhau.
          </p>
        </div>
        <div className="learning-story" ref={story}>
          <div className="story-visual">
            <div className="story-sheet">
              <div className="story-sheet-top">
                <span>MỘT VÍ DỤ NHỎ</span>
                <span>0{step + 1} / 03</span>
              </div>
              <div className="story-content" key={step}>
                <p className="handwritten">{STEPS[step].caption}</p>
                <div className="ten-grid" aria-label="Ba phần mười">
                  {Array.from({ length: 10 }, (_, i) => (
                    <span className={i < 3 ? "filled" : ""} key={i} />
                  ))}
                </div>
                <p className="story-question">{STEPS[step].question}</p>
                <p className={`story-answer ${step === 2 ? "answer-words" : ""}`}>{STEPS[step].answer}</p>
                <Mascot size={92} mood={STEPS[step].mood} />
              </div>
              <div className="story-controls" aria-label="Các bước minh họa">
                {STEPS.map((s, i) => (
                  <button
                    key={s.caption}
                    aria-label={`Xem bước ${i + 1}: ${s.caption}`}
                    aria-pressed={step === i}
                    onClick={() => setStep(i)}
                  >
                    <span />
                  </button>
                ))}
              </div>
              <p className="demo-note">Minh họa cách học · Không phải buổi học thật</p>
            </div>
          </div>
          <div className="story-steps">
            {STEPS.map((s, i) => (
              <article
                key={s.title}
                data-step={i}
                className={step === i ? "story-step is-current" : "story-step"}
              >
                <span className="step-number">0{i + 1}</span>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
                <span className="step-line" />
              </article>
            ))}
          </div>
        </div>
      </section>

      <ProjectBenefits />
      <LearningExperience />
      <BuddyShowcase />

      <section id="curriculum" className="curriculum-section">
        <div className="curriculum-heading" data-reveal>
          <p className="eyebrow">NHỮNG ĐIỀU MÌNH SẼ KHÁM PHÁ</p>
          <h2>
            Từ dấu phẩy nhỏ,
            <br />
            đến <em>những hình hay.</em>
          </h2>
          <p>Hai chương Toán lớp 5. Kiến thức được kết nối để con từng bước xây nền vững hơn.</p>
          <div className="curriculum-stamp" aria-hidden="true">
            <span>Toán</span>
            <strong>5</strong>
            <span>cùng Buddy</span>
          </div>
        </div>
        <div className="lesson-list" data-reveal>
          {LESSONS.map((item, i) => (
            <div className={`lesson-row ${lesson === i ? "is-open" : ""}`} key={item.name}>
              <h3>
                <button
                  aria-expanded={lesson === i}
                  aria-controls={`lesson-preview-${i}`}
                  onClick={() => setLesson(i)}
                >
                  <span className="lesson-index">0{i + 1}</span>
                  <span>{item.name}</span>
                  <span className="lesson-toggle" aria-hidden="true">
                    {lesson === i ? "−" : "+"}
                  </span>
                </button>
              </h3>
              <div id={`lesson-preview-${i}`} className="lesson-body" hidden={lesson !== i}>
                <p>{item.note}</p>
                <blockquote>{item.sample}</blockquote>
                <span className="demo-note">Nội dung giới thiệu bài học</span>
              </div>
            </div>
          ))}
          <button className="text-link curriculum-link" onClick={() => openRole("STUDENT")}>
            Xem chương đang học của con <span aria-hidden="true">↗</span>
          </button>
        </div>
      </section>

      <section id="for-everyone" className="together-section">
        <div className="together-intro" data-reveal>
          <p className="eyebrow">CÓ MỌI NGƯỜI ĐỒNG HÀNH</p>
          <h2>
            Một hành trình.
            <br />
            <em>Ba góc nhìn.</em>
          </h2>
          <p>
            Con có chỗ để thử. Bố mẹ hiểu sự tiến bộ.
            <br />
            Thầy cô biết lúc nào cần giúp.
          </p>
        </div>
        <div className="role-editorial">
          {(
            [
              [
                "STUDENT",
                "01",
                "Dành cho con",
                "Một góc học của riêng mình.",
                "Trò chuyện bằng chữ hoặc giọng nói. Học tiếp bài còn dang dở và xem những điều mình đã làm được.",
                "Vào phòng học",
              ],
              [
                "PARENT",
                "02",
                "Dành cho bố mẹ",
                "Hiểu con, qua từng bước nhỏ.",
                "Xem con học có đều không, đang vững phần nào và cần thêm một chút đồng hành ở đâu.",
                "Xem việc học của con",
              ],
              [
                "TEACHER",
                "03",
                "Dành cho thầy cô",
                "Nhìn rõ để giúp đúng chỗ.",
                "Theo dõi lớp, đọc bằng chứng học tập và quản lý nội dung trước khi đưa vào buổi học.",
                "Mở góc giáo viên",
              ],
            ] as const
          ).map(([role, number, label, title, text, cta]) => (
            <article data-reveal key={role}>
              <span className="editorial-number">{number}</span>
              <p className="eyebrow">{label}</p>
              <h3>{title}</h3>
              <p>{text}</p>
              <button className="text-link" onClick={() => openRole(role)}>
                {cta} <span aria-hidden="true">↗</span>
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="closing-section" data-reveal>
        <span className="handwritten">Không sao nếu con chưa biết.</span>
        <h2>
          Mình bắt đầu
          <br />
          từ <em>một câu hỏi nhé?</em>
        </h2>
        <button className="ink-button" onClick={() => openRole("STUDENT")}>
          Học cùng Buddy <span aria-hidden="true">↗</span>
        </button>
        <Mascot size={135} mood="encouraging" animated />
      </section>
      {askingRole && (
        <PinDialog
          kind={askingRole}
          studentSignup={studentSignup}
          account={accounts.find((a) => a.kind === askingRole)}
          onClose={() => setAskingRole(null)}
          onDone={(kind) => {
            setAskingRole(null);
            loggedIn();
            void navigate(homeOf(kind));
          }}
        />
      )}
    </AppShell>
  );
}
