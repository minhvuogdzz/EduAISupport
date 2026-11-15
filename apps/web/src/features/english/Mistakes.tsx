import type { CSSProperties } from "react";

import type { TypicalMistake } from "../../api/contract";
import "./subjects.css";

const TONES = ["tone-coral", "tone-grape", "tone-sky"];

/**
 * English (ENG-7c, DI-153): the child's typical mistakes on a topic, the most frequent first, each with a
 * short example ("eat → ate") the server draws from a graded answer. Never the child's whole sentence or a
 * score. Renders nothing for math (the field is absent) or when there is no mistake.
 */
export function MistakeList({
  mistakes,
  title = "Lỗi con hay gặp",
}: {
  mistakes?: TypicalMistake[] | null;
  title?: string;
}) {
  if (!mistakes?.length) return null;
  return (
    <div className="mistake-box">
      <p className="mistake-title">{title}</p>
      <ul className="mistake-list">
        {mistakes.map((m, index) => (
          <li
            key={m.label}
            className={`mistake-item ${TONES[index % TONES.length]}`}
            style={{ "--i": index } as CSSProperties}
          >
            <span className="mistake-label">
              {m.label}
              <span className="mistake-count">{m.count} lần</span>
            </span>
            {m.examples.map((example) => (
              <span key={example} className="mistake-example">
                {example}
              </span>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}
