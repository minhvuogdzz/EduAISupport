import { useEffect, useState, type CSSProperties } from "react";
import { Link, useNavigate } from "react-router";

import type { AccountKind } from "../api/contract";
import { AppShell, PinDialog } from "../components/AppShell";
import { Burst } from "../components/Burst";
import { ArrowRightIcon, BookIcon, ChartIcon, UsersIcon } from "../components/icons";
import { Mascot } from "../components/Mascot";
import { homeOf, useAuth } from "../features/auth/authContext";
import { BuddyShowcase } from "./BuddyShowcase";
import { LearningExperience } from "./LearningExperience";
import { ProjectBenefits } from "./ProjectBenefits";
import { Curriculum, SubjectsShowcase } from "./SubjectsShowcase";
import { Wave } from "./Wave";
import "./home.css";

const PROMISES = [
  ["Con tự tìm ra cách làm", "Buddy gợi mở từng bước, không vội đưa lời giải.", "tone-sun"],
  ["Tiến bộ có bằng chứng", "Nhìn cả cách con nghĩ, không chỉ đáp án cuối.", "tone-leaf"],
  ["Thầy cô giữ định hướng", "Nội dung được quản lý và có bước duyệt.", "tone-grape"],
];

const DOODLES = ["0,3", "+", "A", "½", "Hi!", "×", "b", "?"];

const ROLES = [
  {
    role: "STUDENT",
    Icon: BookIcon,
    tone: "tone-sky",
    label: "Dành cho con",
    title: "Một góc học của riêng mình.",
    text: "Trò chuyện bằng chữ hoặc giọng nói, học tiếp bài còn dang dở và xem những điều mình đã làm được.",
    points: ["Gợi mở từng bước", "Chữ và giọng nói"],
    cta: "Vào phòng học",
  },
  {
    role: "PARENT",
    Icon: UsersIcon,
    tone: "tone-coral",
    label: "Dành cho bố mẹ",
    title: "Hiểu con, qua từng bước nhỏ.",
    text: "Xem con học có đều không, đang vững phần nào và cần thêm một chút đồng hành ở đâu.",
    points: ["Xu hướng học tập", "Gợi ý giúp con ở nhà"],
    cta: "Xem việc học của con",
  },
  {
    role: "TEACHER",
    Icon: ChartIcon,
    tone: "tone-leaf",
    label: "Dành cho thầy cô",
    title: "Nhìn rõ để giúp đúng chỗ.",
    text: "Theo dõi lớp, đọc bằng chứng học tập và quản lý nội dung trước khi đưa vào buổi học.",
    points: ["Bản đồ kiến thức", "Báo cáo từng em"],
    cta: "Mở góc giáo viên",
  },
] as const;

/** Tap Buddy and Buddy jumps for joy: the first thing a child can play with on the page. */
function HeroBuddy() {
  const [fire, setFire] = useState(0);
  const [cheering, setCheering] = useState(false);
  useEffect(() => {
    if (!cheering) return;
    const timer = window.setTimeout(() => setCheering(false), 1400);
    return () => window.clearTimeout(timer);
  }, [cheering, fire]);
  return (
    <button
      type="button"
      className="hm-buddy"
      aria-label="Chạm vào Buddy"
      onClick={() => {
        setFire((value) => value + 1);
        setCheering(true);
      }}
    >
      <span className="hm-hop" key={fire}>
        <Mascot size={320} mood={cheering ? "celebrating" : "happy"} animated />
      </span>
      <Burst fire={fire} />
    </button>
  );
}

export function HomePage() {
  const { user, accounts, switchTo, loggedIn, studentSignup } = useAuth();
  const navigate = useNavigate();
  const [askingRole, setAskingRole] = useState<AccountKind | null>(null);
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

      <section className="hm-hero">
        <span className="hm-cloud hm-cloud-one" aria-hidden="true" />
        <span className="hm-cloud hm-cloud-two" aria-hidden="true" />
        <span className="hm-doodles" aria-hidden="true">
          {DOODLES.map((doodle, index) => (
            <i key={doodle} style={{ "--i": index } as CSSProperties}>
              {doodle}
            </i>
          ))}
        </span>
        <div className="hm-hero-inner">
          <div className="hm-hero-copy">
            <p className="hm-kicker hero-enter">Người bạn học của con · Lớp 5</p>
            <h1 className="hero-enter">
              Mỗi ngày, con <mark>hiểu thêm</mark> một chút.
            </h1>
            <p className="hm-hero-lead hero-enter">
              Monkey Buddy không vội đưa đáp án. Buddy hỏi, gợi mở và chờ con tự nghĩ, từ bài Toán đến những
              câu tiếng Anh đầu tiên.
            </p>
            <div className="hm-actions hero-enter">
              <button className="hm-button" onClick={() => openRole("STUDENT")}>
                Vào học cùng Buddy <ArrowRightIcon />
              </button>
              <a className="hm-button-ghost" href="#subjects">
                Xem các môn học
              </a>
            </div>
          </div>
          <div className="hm-stage">
            <span className="hm-stage-blob" aria-hidden="true" />
            <HeroBuddy />
            <div className="hm-float hm-float-math" aria-hidden="true">
              <small>Toán</small>
              <span className="hm-mini-bar">
                {Array.from({ length: 10 }, (_, i) => (
                  <i key={i} className={i < 3 ? "is-on" : ""} />
                ))}
              </span>
              <strong>3/10 = 0,3</strong>
            </div>
            <div className="hm-float hm-float-english" aria-hidden="true">
              <small>Tiếng Anh</small>
              <strong lang="en">Hello!</strong>
              <span>Xin chào!</span>
            </div>
            <div className="hm-float hm-float-ask" aria-hidden="true">
              Chạm vào mình đi!
            </div>
          </div>
        </div>
        <Wave colour="#ffffff" />
      </section>

      <section className="hm-promises" aria-label="Điều Monkey Edu giữ">
        {PROMISES.map(([title, text, tone], index) => (
          <article key={title} className={tone} data-reveal>
            <span>{index + 1}</span>
            <div>
              <h2>{title}</h2>
              <p>{text}</p>
            </div>
          </article>
        ))}
      </section>

      <SubjectsShowcase />
      <LearningExperience />

      <section id="for-everyone" className="hm-section">
        <div className="hm-intro" data-reveal>
          <p className="hm-kicker">Có mọi người đồng hành</p>
          <h2>
            Một hành trình, <mark>ba góc nhìn.</mark>
          </h2>
          <p>Con có chỗ để thử. Bố mẹ hiểu sự tiến bộ. Thầy cô biết lúc nào cần giúp.</p>
        </div>
        <div className="hm-roles">
          {ROLES.map(({ role, Icon, tone, label, title, text, points, cta }) => (
            <article key={role} className={`hm-role ${tone}`} data-reveal>
              <span className="en-badge en-badge-large">
                <Icon />
              </span>
              <p className="hm-role-label">{label}</p>
              <h3>{title}</h3>
              <p>{text}</p>
              <ul>
                {points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
              <button onClick={() => openRole(role)}>
                {cta} <ArrowRightIcon />
              </button>
            </article>
          ))}
        </div>
      </section>

      <ProjectBenefits />
      <BuddyShowcase />
      <Curriculum onOpenStudent={() => openRole("STUDENT")} />

      <section className="hm-closing" data-reveal>
        <div>
          <p className="hm-kicker">Không sao nếu con chưa biết</p>
          <h2>Mình bắt đầu từ một câu hỏi nhé?</h2>
          <div className="hm-actions">
            <button className="hm-button" onClick={() => openRole("STUDENT")}>
              Học cùng Buddy <ArrowRightIcon />
            </button>
            <Link className="hm-button-ghost" to="/student/english">
              Xem trước Tiếng Anh
            </Link>
          </div>
        </div>
        <Mascot size={180} mood="encouraging" animated />
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
