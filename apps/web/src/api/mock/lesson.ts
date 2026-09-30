import rawLesson from "virtual:cavat/mock-lesson";

import type { ActivityType, HintLevel } from "../contract";
import type { LessonItem, LessonPackage, Misconception, OpenItem } from "./lessonTypes";

function toLesson(value: unknown): LessonPackage {
  if (typeof value !== "object" || value === null || !Array.isArray((value as { items?: unknown }).items)) {
    throw new Error("virtual:cavat/mock-lesson did not provide a lesson package");
  }
  return value as LessonPackage;
}

/** Lesson 1 from docs/pedagogy (DRAFT until the owner approves it), EXIT items sealed at build time. */
export const LESSON: LessonPackage = toLesson(rawLesson);

export interface PlanStep {
  activity_id: string;
  type: ActivityType;
  item_ids: string[];
}

/**
 * Activity plan of every mock session: the minimal plan of T08 (CONCEPT_CHECK → GUIDED_PRACTICE →
 * EXIT_ASSESSMENT → SUMMARY) over a few items of lesson 1. Activity ids follow the contract example in
 * blueprint PART 17.2.
 */
export const MOCK_PLAN: readonly PlanStep[] = [
  { activity_id: "A3", type: "CONCEPT_CHECK", item_ids: ["CC-01", "CC-02"] },
  { activity_id: "A5", type: "GUIDED_PRACTICE", item_ids: ["GP-01", "GP-02", "GP-08", "GP-09"] },
  { activity_id: "A7", type: "EXIT_ASSESSMENT", item_ids: ["EX-01", "EX-03"] },
  { activity_id: "A8", type: "SUMMARY", item_ids: [] },
];

export const PLAN_ITEM_COUNT = MOCK_PLAN.reduce((total, step) => total + step.item_ids.length, 0);

/** Highest hint level per activity (T02 HintPolicyConfig; contract hintPolicy in PART 17.2). */
const HINT_CAP: Partial<Record<ActivityType, HintLevel>> = {
  CONCEPT_CHECK: 3,
  GUIDED_PRACTICE: 7,
  INDEPENDENT_PRACTICE: 5,
  EXIT_ASSESSMENT: 1,
};

export function hintCap(activity: ActivityType): HintLevel {
  return HINT_CAP[activity] ?? 3;
}

export function lessonItem(lesson: LessonPackage, itemId: string): LessonItem {
  const item = lesson.items.find((it) => it.id === itemId);
  if (!item) throw new Error(`item ${itemId} is not in lesson ${lesson.lesson_id}`);
  return item;
}

export function findMisconception(lesson: LessonPackage, id: string): Misconception | undefined {
  return lesson.misconceptions.find((m) => m.id === id);
}

/** Another practice item of the same isomorphic group, used as a "similar example". */
export function siblingOf(lesson: LessonPackage, item: OpenItem): OpenItem | undefined {
  if (!item.isomorphic_group) return undefined;
  return lesson.items.find(
    (it): it is OpenItem =>
      it.purpose !== "EXIT" && it.id !== item.id && it.isomorphic_group === item.isomorphic_group,
  );
}
