import type { CSSProperties } from "react";
import { useSearchParams } from "react-router";

import { AppShell } from "../../components/AppShell";
import { Mascot } from "../../components/Mascot";
import { ENGLISH_UNITS, SAMPLE_CHILD_LEVELS } from "./content";
import { LEVEL_TONE } from "./levels";
import { SubjectSwitch } from "./SubjectSwitch";
import "./subjects.css";

/** What a parent will see of English. There is no English data yet, so every level is a labelled sample. */
export function ParentEnglishPage() {
  const [params] = useSearchParams();
  const code = params.get("code");
  return (
    <AppShell>
      <title>Tiếng Anh của con · Monkey Edu</title>
      <div className="subject-page">
        <SubjectSwitch
          current="english"
          mathTo={code ? `/parent/${code}` : "/parent"}
          englishTo={code ? `/parent/english?code=${code}` : "/parent/english"}
        />
        <section className="en-hero" aria-labelledby="parent-english-title">
          <div className="en-hero-copy">
            <p className="preview-chip">Bản xem trước · Tiếng Anh</p>
            <h1 id="parent-english-title">Tiếng Anh của con</h1>
            <p className="en-hero-note">
              Khi môn Tiếng Anh mở, bố mẹ sẽ thấy con đang ở chủ đề nào và cần giúp gì. Các mức dưới đây là
              minh họa, chưa phải kết quả của con.
            </p>
          </div>
          <div className="en-hero-buddy">
            <Mascot mood="encouraging" size={150} animated />
          </div>
        </section>

        <section aria-labelledby="parent-topics-title">
          <h2 id="parent-topics-title" className="subject-heading">
            Mức hiểu từng chủ đề (minh họa)
          </h2>
          <ul className="en-rows">
            {ENGLISH_UNITS.map((unit, index) => (
              <li key={unit.id} className={unit.tone} style={{ "--i": index } as CSSProperties}>
                <span className="en-badge">
                  <unit.icon />
                </span>
                <span className="en-row-name">
                  <strong lang="en">{unit.title}</strong>
                  <small>{unit.subtitle}</small>
                </span>
                <span className={`level ${LEVEL_TONE[SAMPLE_CHILD_LEVELS[index]]}`}>
                  {SAMPLE_CHILD_LEVELS[index]}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="en-tip" aria-labelledby="parent-home-title">
          <h2 id="parent-home-title">Bố mẹ có thể giúp con ở nhà</h2>
          <p>
            Thử hỏi con <strong lang="en">“{ENGLISH_UNITS[0].phrases[0].en}”</strong> rồi chờ con tự trả lời.
            Khi bài học mở, gợi ý này sẽ theo đúng chủ đề con đang học.
          </p>
        </section>
      </div>
    </AppShell>
  );
}
