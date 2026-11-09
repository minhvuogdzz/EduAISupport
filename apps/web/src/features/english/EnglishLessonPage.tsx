import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from "react";
import { Link, useParams } from "react-router";

import { AppShell } from "../../components/AppShell";
import { Burst } from "../../components/Burst";
import { ArrowRightIcon, SendIcon } from "../../components/icons";
import { Mascot } from "../../components/Mascot";
import { ENGLISH_SKILLS, ENGLISH_UNITS, type EnglishUnit } from "./content";
import { SubjectSwitch } from "./SubjectSwitch";
import "./subjects.css";

/** One English topic in preview: its words and phrases, and a chat where the teacher is still preparing. */
export function EnglishLessonPage() {
  const { unitId } = useParams();
  const unit = ENGLISH_UNITS.find((item) => item.id === unitId);
  return (
    <AppShell>
      <title>{`${unit?.title ?? "Tiếng Anh"} · Monkey Edu`}</title>
      <div className="subject-page">
        <SubjectSwitch current="english" />
        {unit ? (
          <Lesson unit={unit} key={unit.id} />
        ) : (
          <p role="alert" className="en-missing">
            Chưa có chủ đề này. <Link to="/student/english">Về các chủ đề Tiếng Anh</Link>
          </p>
        )}
      </div>
    </AppShell>
  );
}

function WordCard({ word, meaning, index }: { word: string; meaning: string; index: number }) {
  const [open, setOpen] = useState(false);
  const [fire, setFire] = useState(0);
  return (
    <li style={{ "--i": index } as CSSProperties}>
      <button
        type="button"
        className={`flip-card ${open ? "is-open" : ""}`}
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
    </li>
  );
}

function Lesson({ unit }: { unit: EnglishUnit }) {
  const index = ENGLISH_UNITS.indexOf(unit);
  const next = ENGLISH_UNITS[index + 1];
  return (
    <>
      <Link to="/student/english" className="en-back">
        <ArrowRightIcon />
        Tất cả chủ đề
      </Link>
      <section className={`en-lesson-head ${unit.tone}`} aria-labelledby="unit-title">
        <span className="en-badge en-badge-large">
          <unit.icon />
        </span>
        <div>
          <p className="preview-chip">
            Bản xem trước · Chủ đề {index + 1}/{ENGLISH_UNITS.length}
          </p>
          <h1 id="unit-title" lang="en">
            {unit.title}
          </h1>
          <p className="en-lesson-sub">{unit.subtitle}</p>
          <p className="en-lesson-goal">
            <strong>Mục tiêu:</strong> {unit.goal}
          </p>
        </div>
      </section>

      <div className="en-lesson-grid">
        <div className="en-lesson-main">
          <section aria-labelledby="words-title" className={unit.tone}>
            <h2 id="words-title" className="subject-heading">
              Từ mới
            </h2>
            <ul className="en-words">
              {unit.words.map((item, wordIndex) => (
                <WordCard key={item.word} word={item.word} meaning={item.meaning} index={wordIndex} />
              ))}
            </ul>
          </section>

          <section aria-labelledby="phrases-title">
            <h2 id="phrases-title" className="subject-heading">
              Câu nói hay dùng
            </h2>
            <ul className="en-phrases">
              {unit.phrases.map((phrase) => (
                <li key={phrase.en}>
                  <strong lang="en">{phrase.en}</strong>
                  <span>{phrase.vi}</span>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="path-title">
            <h2 id="path-title" className="subject-heading">
              Lộ trình của bài
            </h2>
            <ol className="en-path">
              {ENGLISH_SKILLS.map((skill) => (
                <li key={skill.name} className={skill.tone}>
                  <span className="en-badge">
                    <skill.icon />
                  </span>
                  <strong>{skill.label}</strong>
                  <small>Cô đang soạn</small>
                </li>
              ))}
            </ol>
          </section>

          {next && (
            <Link to={`/student/english/${next.id}`} className="en-next">
              <span>
                <small>Chủ đề tiếp theo</small>
                <strong lang="en">{next.title}</strong>
              </span>
              <ArrowRightIcon />
            </Link>
          )}
        </div>
        <PreviewChat unit={unit} />
      </div>
    </>
  );
}

/**
 * The look of the English tutor before it exists. A question stays in this component: nothing reaches a
 * server or a model, and the only reply is that the lesson is being prepared.
 */
function PreviewChat({ unit }: { unit: EnglishUnit }) {
  const [draft, setDraft] = useState("");
  const [asked, setAsked] = useState<string[]>([]);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [asked]);

  const ask = (question: string) => {
    const text = question.trim();
    if (text) setAsked((list) => [...list, text]);
    setDraft("");
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    ask(draft);
  };

  return (
    <aside className="en-chat" aria-label="Hỏi cô Buddy">
      <header className="en-chat-head">
        <Mascot mood={asked.length > 0 ? "thinking" : "happy"} size={64} animated />
        <span>
          <strong>Cô Buddy</strong>
          <small>Đang soạn bài Tiếng Anh</small>
        </span>
      </header>
      <div className="en-chat-log" ref={scroller}>
        <div role="log" aria-label="Hội thoại" className="en-chat-messages">
          <p className="en-bubble en-bubble-tutor">
            <span lang="en">Hello!</span> Con muốn hỏi gì về chủ đề <span lang="en">{unit.title}</span> nào?
          </p>
          {asked.map((question, index) => (
            <p key={index} className="en-bubble en-bubble-student">
              {question}
            </p>
          ))}
        </div>
        <div role="status">
          {asked.length > 0 && (
            <div className="en-preparing">
              <span className="en-dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              <p>
                <strong>Cô đang chuẩn bị bài giảng</strong>
                <span>Trong lúc chờ, con lật thẻ từ mới bên cạnh nhé!</span>
              </p>
            </div>
          )}
        </div>
      </div>
      {asked.length === 0 && (
        <div className="en-starters">
          {unit.starters.map((starter) => (
            <button key={starter} type="button" onClick={() => ask(starter)}>
              {starter}
            </button>
          ))}
        </div>
      )}
      <form className="en-chat-form" onSubmit={submit}>
        <label htmlFor="english-question" className="sr-only">
          Câu hỏi của con
        </label>
        <input
          id="english-question"
          value={draft}
          autoComplete="off"
          placeholder="Con hỏi cô ở đây..."
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            // Enter that finishes a Telex or VNI composition must not send the question.
            if (event.key === "Enter" && event.nativeEvent.isComposing) event.preventDefault();
          }}
        />
        <button type="submit" aria-label="Gửi câu hỏi" disabled={!draft.trim()}>
          <SendIcon />
        </button>
      </form>
    </aside>
  );
}
