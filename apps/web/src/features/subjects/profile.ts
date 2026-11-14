import type { Dimension, ItemResolution, Subject } from "../../api/contract";
import { DIMENSION_LABEL, LEVEL_NAME, RESOLUTION_LABEL } from "../../components/labels";

/**
 * What changes between subjects on the shared pages (english-module-rules F2): words, labels of the
 * framework and the paths of each role's area. The data still comes from the API; nothing here is a score,
 * a threshold or a formula. The math profile holds the exact words the math pages have always shown.
 */
export interface SubjectProfile {
  id: Subject;
  /** "Toán", "Tiếng Anh". */
  name: string;
  /** The word for a chapter of this subject: "chương", "unit". */
  unit: string;
  /**
   * A chapter by its title, in a sentence: "chương Số thập phân"; an English unit's title already says
   * "Unit 11: …", so it is said alone.
   */
  chapterName: (title: string) => string;
  /** The same at the start of a sentence: "Chương Số thập phân". */
  ChapterName: (title: string) => string;
  /** The framework a method note cites before its section number: "khung Toán §46". */
  framework: string;
  /** The chapter the English pages ask for until the server lists its units (ENG-7b). */
  defaultChapter?: string;
  /** The seven dimensions C R A T I S D with the meaning they have in this subject (teacher only). */
  dimensionLabel: Record<Dimension, string>;
  /** One sentence per dimension: what counts as evidence (ADR-060 §4); math keeps its short labels. */
  dimensionHelp?: Record<Dimension, string>;
  /** The six levels of understanding (§4–§8), named for this subject (teacher only). */
  levelName: readonly string[];
  /** How an item ended, for the teacher (DI-114 for English). */
  resolutionLabel: Record<ItemResolution, string>;
  /** The student's and the parent's words (DI-113): never a score. */
  words: {
    studentGoingWell: string;
    studentToPractise: string;
    nextGoal: string;
  };
  paths: {
    student: string;
    session: (sessionId: string) => string;
    teacher: string;
    teacherStudent: string;
    parent: string;
  };
  /** Where the device remembers the last session of this subject ("Học tiếp"). */
  lastSessionKey: string;
}

export const MATH_PROFILE: SubjectProfile = {
  id: "math",
  name: "Toán",
  unit: "chương",
  chapterName: (title) => `chương ${title}`,
  ChapterName: (title) => `Chương ${title}`,
  framework: "khung Toán",
  dimensionLabel: DIMENSION_LABEL,
  levelName: LEVEL_NAME,
  resolutionLabel: RESOLUTION_LABEL,
  words: {
    studentGoingWell: "Con đã làm tốt",
    studentToPractise: "Cần luyện thêm",
    nextGoal: "Mục tiêu tiếp theo",
  },
  paths: {
    student: "/student",
    session: (id) => `/student/sessions/${id}`,
    teacher: "/teacher",
    teacherStudent: "/teacher/students",
    parent: "/parent",
  },
  lastSessionKey: "cavat.student.last-session",
};

/** The English unit (D-T13): Unit 11 "Family time", the chapter id ENG-3 gave it. */
export const ENGLISH_UNIT_ID = "eng-g5-u11-family-time";

export const ENGLISH_PROFILE: SubjectProfile = {
  id: "english",
  name: "Tiếng Anh",
  unit: "unit",
  chapterName: (title) => title,
  ChapterName: (title) => title,
  framework: "khung đánh giá Tiếng Anh (ADR-060)",
  defaultChapter: ENGLISH_UNIT_ID,
  // ADR-060 §4: the same seven dimensions, read for the content of one English unit.
  dimensionLabel: {
    C: "Dùng đúng từ, mẫu câu",
    R: "Hiểu vì sao",
    A: "Dùng trong bài",
    T: "Bối cảnh mới",
    I: "Tự làm",
    S: "Còn nhớ",
    D: "Sửa câu sai",
  },
  dimensionHelp: {
    C: "Nhận biết và dùng đúng từ, đúng mẫu câu (câu mức A, B).",
    R: "Nói được vì sao: hỏi bằng did thì đáp bằng did, kể chuyện đã qua thì đổi động từ (câu mức C, “vì sao”, “con nói lại”).",
    A: "Dùng mẫu câu trong tình huống của bài (câu mức D).",
    T: "Dùng ở bối cảnh mới, ghép hai mẫu (câu mức E); có thể trống khi tài liệu không có câu này.",
    I: "Tự làm, không cần gợi ý (thang gợi ý H0–H7 của DI-112).",
    S: "Còn nhớ sau vài ngày: chỉ tính từ câu kiểm tra lại, chưa có nên để trống.",
    D: "Phát hiện và sửa câu sai (câu tìm lỗi).",
  },
  // ADR-060 §8: the six levels read for the English content.
  levelName: [
    "Chưa nhận ra từ, mẫu câu",
    "Nhận ra cụm từ",
    "Nói theo mẫu khi có gợi ý",
    "Tự dùng đúng và biết vì sao",
    "Dùng được trong tình huống",
    "Vững trong buổi ôn",
  ],
  // DI-114: four groups, the first three never merged into "đúng".
  resolutionLabel: {
    INDEPENDENT: "Tự làm",
    SUPPORTED: "Nhờ gợi ý",
    WORKED: "Sau khi cô đọc mẫu",
    UNRESOLVED: "Chưa xong",
  },
  // ADR-060 §8, DI-113: "Con đã nói được / Mình ôn thêm nhé / Mục tiêu tiếp theo".
  words: {
    studentGoingWell: "Con đã nói được",
    studentToPractise: "Mình ôn thêm nhé",
    nextGoal: "Mục tiêu tiếp theo",
  },
  paths: {
    student: "/student/english",
    session: (id) => `/student/english/sessions/${id}`,
    teacher: "/teacher/english",
    teacherStudent: "/teacher/english/students",
    parent: "/parent/english",
  },
  lastSessionKey: "cavat.student.last-session.english",
};

export const PROFILES: Record<Subject, SubjectProfile> = { math: MATH_PROFILE, english: ENGLISH_PROFILE };

/** The profile of a session or a chapter whose subject may be missing (rule S4: missing means math). */
export function profileOf(subject: Subject | null | undefined): SubjectProfile {
  return PROFILES[subject ?? "math"];
}
