import type { CSSProperties } from "react";
import { Link } from "react-router";

import { AppShell } from "../../components/AppShell";
import { ArrowRightIcon } from "../../components/icons";
import { Mascot } from "../../components/Mascot";
import { useAuth } from "../auth/authContext";
import { ENGLISH_SKILLS, ENGLISH_UNITS } from "./content";
import { SubjectSwitch } from "./SubjectSwitch";
import "./subjects.css";

const DOODLES = ["A", "b", "C", "Hi!", "?", "z"];

/** The English corner: a preview of the module. It shows topics only, with no tutor or progress behind it. */
export function EnglishHomePage() {
  const { user } = useAuth();
  const first = ENGLISH_UNITS[0];
  return (
    <AppShell>
      <title>Tiếng Anh · Monkey Edu</title>
      <div className="subject-page">
        <SubjectSwitch current="english" />

        <section className="en-hero" aria-labelledby="english-title">
          <span className="en-doodles" aria-hidden="true">
            {DOODLES.map((doodle, index) => (
              <i key={doodle} style={{ "--i": index } as CSSProperties}>
                {doodle}
              </i>
            ))}
          </span>
          <div className="en-hero-copy">
            <p className="preview-chip">Bản xem trước · Tiếng Anh lớp 5</p>
            <h1 id="english-title">
              <span lang="en">Hello</span>
              {user?.display_name ? `, ${user.display_name}` : ""}! Mình cùng nói tiếng Anh nhé?
            </h1>
            <p className="en-hero-note">
              Sáu chủ đề gần gũi, đi từ lời chào đến chuyện quanh nhà. Con xem trước từ mới trong khi cô soạn
              bài.
            </p>
            <Link to={`/student/english/${first.id}`} className="en-primary">
              Xem chủ đề đầu tiên <ArrowRightIcon />
            </Link>
          </div>
          <div className="en-hero-buddy">
            <span className="en-hero-bubble" lang="en">
              Hello!
            </span>
            <Mascot mood="happy" size={170} animated />
          </div>
        </section>

        <section aria-labelledby="skills-title">
          <h2 id="skills-title" className="subject-heading">
            Bốn kỹ năng con sẽ luyện
          </h2>
          <ul className="en-skills">
            {ENGLISH_SKILLS.map((skill, index) => (
              <li key={skill.name} className={skill.tone} style={{ "--i": index } as CSSProperties}>
                <span className="en-badge">
                  <skill.icon />
                </span>
                <span>
                  <strong>{skill.label}</strong>
                  <small>{skill.note}</small>
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="units-title">
          <h2 id="units-title" className="subject-heading">
            Các chủ đề
          </h2>
          <ol className="en-units">
            {ENGLISH_UNITS.map((unit, index) => (
              <li key={unit.id} style={{ "--i": index } as CSSProperties}>
                <Link to={`/student/english/${unit.id}`} className={`en-unit ${unit.tone}`}>
                  <span className="en-unit-top">
                    <span className="en-badge">
                      <unit.icon />
                    </span>
                    <span className="en-unit-number">Chủ đề {index + 1}</span>
                  </span>
                  <strong lang="en">{unit.title}</strong>
                  <span className="en-unit-subtitle">{unit.subtitle}</span>
                  <span className="en-unit-words" lang="en">
                    {unit.words.slice(0, 3).map((item) => (
                      <span key={item.word}>{item.word}</span>
                    ))}
                  </span>
                  <span className="en-unit-go">
                    Xem chủ đề <ArrowRightIcon />
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </AppShell>
  );
}
