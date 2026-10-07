/**
 * The lesson package as the mock API receives it: a TypeScript view of
 * services/api/cavat/modules/content/lesson_package.py, limited to the fields the mock reads.
 */
import type { AnswerFormat, HintLevel, HintTarget } from "../contract";

export interface HintTemplate {
  target: HintTarget;
  level: HintLevel;
  text: string;
  /** Kinds of item a generic hint fits (ADR-019); none: every kind. */
  answer_types?: string[];
}

export interface CompareAnswer {
  type: "compare";
  left: string;
  right: string;
}

export interface OrderAnswer {
  type: "order";
  numbers: string[];
  direction?: "asc" | "desc";
}

export interface NumericAnswer {
  type: "numeric";
  value: string;
  /** Wrong answers that reveal a misconception, e.g. {"1": "DEC-M01"}. */
  wrong_answers?: Record<string, string>;
}

export interface ChoiceOption {
  id: string;
  text: string;
  correct?: boolean;
  aliases?: string[];
  misconceptions?: string[];
  misconception_confidence?: number;
  /** Follow-up question that separates two causes of this wrong option (lesson_package.Probe). The mock ignores it. */
  probe?: { prompt: string; left: string; right: string; if_wrong: string; if_correct: string };
}

export interface ChoiceAnswer {
  type: "choice";
  options: ChoiceOption[];
}

export interface BooleanAnswer {
  type: "boolean";
  value: boolean;
  requires_explanation?: boolean;
  /** Keys "true"/"false": the wrong verdict that reveals a misconception. */
  wrong_answers?: Record<string, string>;
}

export interface OpenAnswer {
  type: "open";
  rubric: string;
  sample_answer: string;
}

export type AnswerSpec =
  CompareAnswer | OrderAnswer | NumericAnswer | ChoiceAnswer | BooleanAnswer | OpenAnswer;

/** CONCEPT_CHECK / PRACTICE / REVIEW items arrive complete: the mock grades them in the browser. */
export interface OpenItem {
  id: string;
  purpose: "CONCEPT_CHECK" | "PRACTICE" | "REVIEW";
  kc_ids: string[];
  stem: string;
  answer: AnswerSpec;
  hints: HintTemplate[];
  worked_solution?: string[];
  explanation?: string | null;
  isomorphic_group?: string | null;
  rephrase?: string | null;
  verify_prompt?: string | null;
}

/**
 * EXIT items arrive sealed by vite-plugins/mockLesson.ts: the answer type and choice labels only, and
 * H1 hints at most. The mock therefore cannot grade them, by design.
 */
export interface SealedItem {
  id: string;
  purpose: "EXIT";
  kc_ids: string[];
  stem: string;
  answer: { type: AnswerFormat; options?: { id: string; text: string }[] };
  hints: HintTemplate[];
}

export type LessonItem = OpenItem | SealedItem;

export interface Misconception {
  id: string;
  kc_id: string;
  name: string;
  description: string;
  counter_examples: string[];
}

export interface LessonPackage {
  lesson_id: string;
  version: string;
  status: string;
  title: string;
  persona: { tutor_self: string; student_address: string };
  misconceptions: Misconception[];
  generic_hints: HintTemplate[];
  items: LessonItem[];
}
