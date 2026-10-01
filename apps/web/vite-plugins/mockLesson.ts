/**
 * Build-time bridge from the lesson package YAML to the in-browser mock API.
 *
 * The mock API (src/api/mock) imports `virtual:cavat/mock-lesson`. This plugin serves that module from
 * docs/pedagogy/<subject>/<lesson>/lesson.yaml, so the YAML stays the single source of truth (no copied
 * fixture that drifts), and it seals every EXIT item on the way: assessment answers never reach the
 * client bundle (CLAUDE.md, design rule 2).
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import type { Plugin } from "vite";
import { parse } from "yaml";

export const MOCK_LESSON_ID = "virtual:cavat/mock-lesson";
const RESOLVED_ID = `\0${MOCK_LESSON_ID}`;

/** Lesson 1 (Math G5, "So sánh hai số thập phân"): the only lesson in scope for the mock. */
export const DEFAULT_LESSON_PATH = fileURLToPath(
  new URL("../../../docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml", import.meta.url),
);

// Highest hint level an EXIT_ASSESSMENT item may use (blueprint PART 15.2, R-ASSESS-CAP).
const EXIT_HINT_CAP = 1;

type Json = Record<string, unknown>;

const isObject = (value: unknown): value is Json =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/** What the client may know about an EXIT item: enough to render it, nothing to grade it. */
function sealExitItem(item: Json): Json {
  const answer = isObject(item.answer) ? item.answer : {};
  const sealed: Json = { type: answer.type };
  if (answer.type === "choice" && Array.isArray(answer.options)) {
    sealed.options = answer.options.filter(isObject).map((option) => ({ id: option.id, text: option.text }));
  }
  const hints = Array.isArray(item.hints)
    ? item.hints.filter(
        (hint) => isObject(hint) && typeof hint.level === "number" && hint.level <= EXIT_HINT_CAP,
      )
    : [];
  return {
    id: item.id,
    purpose: item.purpose,
    kc_ids: item.kc_ids,
    cognitive_level: item.cognitive_level,
    difficulty: item.difficulty,
    stem: item.stem,
    answer: sealed,
    hints,
  };
}

/** Returns the lesson with every EXIT item reduced to a whitelist of fields; other items are unchanged. */
export function sealAssessmentItems(lesson: unknown): Json {
  if (!isObject(lesson) || !Array.isArray(lesson.items)) {
    throw new Error("lesson package must be a mapping with an `items` list");
  }
  const items = lesson.items
    .filter(isObject)
    .map((item) => (item.purpose === "EXIT" ? sealExitItem(item) : item));
  return { ...lesson, items };
}

export function mockLessonPlugin(lessonPath: string = DEFAULT_LESSON_PATH): Plugin {
  return {
    name: "cavat-mock-lesson",
    resolveId(id) {
      return id === MOCK_LESSON_ID ? RESOLVED_ID : undefined;
    },
    load(id) {
      if (id !== RESOLVED_ID) return undefined;
      this.addWatchFile(lessonPath);
      const lesson = sealAssessmentItems(parse(readFileSync(lessonPath, "utf8")));
      return `export default ${JSON.stringify(lesson)};`;
    },
  };
}
