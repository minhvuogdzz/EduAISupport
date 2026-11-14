/**
 * The reports of the English unit on fixed demo data (ENG-7a, mock only). Three demo students with a few
 * days of Unit 11 each. The numbers are made up but follow the rules the server applies (ADR-060): levels
 * by the bands of §4–§8, the groups of DI-27, the qualitative states of DI-113, the four groups and the
 * three ASR levels of DI-114, `ASR_LOW` at ≥ 40% of ≥ 5 spoken turns in 7 days. They exist so the English
 * pages can be seen and tested before the server computes them (ENG-7b); nothing here is a real student.
 */
import type {
  AttentionReason,
  ClassMisconception,
  ClassOverview,
  ClassStudent,
  Dimension,
  JourneyStep,
  KcGroup,
  MasteryCell,
  NodeStatus,
  ParentChildView,
  ProgressNode,
  ProgressTopic,
  Quality,
  Recommendation,
  StudentOverview,
  TeacherNodeDetail,
  TeacherStudentView,
  VoiceTurn,
} from "../../contract";
import { DIMENSIONS } from "../../contract";
import { MISCONCEPTIONS, NODES, RELATIONS, UNIT } from "./unit11";

const MIN_MASTERY = 75; // DI-15, kept for English (ADR-060 §6)
const STATES = [
  "NOT_LEARNED",
  "RECOGNITION",
  "PROCEDURAL",
  "CONCEPTUAL",
  "APPLIED",
  "PROVISIONALLY_MASTERED",
];

interface DemoNode {
  m: number | null;
  conf: number;
  passed: boolean;
  status: NodeStatus;
  items?: number;
  solved?: number;
  attempts?: number;
  hints?: number;
  seconds?: number;
  mis?: { id: string; count: number; status: "ACTIVE" | "RESOLVING" | "RESOLVED" }[];
}

interface DemoStudent {
  student_id: string;
  display_name: string;
  parent_code: string;
  /** Days ago of each study day, oldest first, and overall M at the end of it. */
  days: { ago: number; mastery: number; voice: number; low: number; passed: number }[];
  nodes: Record<string, DemoNode>;
  step: number;
  sessions: { total: number; completed: number; unfinished: number; minutes: number };
  voiceShare: number;
}

const off: DemoNode = { m: null, conf: 0, passed: false, status: "LOCKED" };

export const DEMO_STUDENTS: DemoStudent[] = [
  {
    student_id: "demo-an",
    display_name: "An",
    parent_code: "A1B2C3",
    step: 4,
    sessions: { total: 4, completed: 3, unfinished: 1, minutes: 58 },
    voiceShare: 45,
    days: [
      { ago: 9, mastery: 24, voice: 0, low: 0, passed: 0 },
      { ago: 6, mastery: 49, voice: 1, low: 0, passed: 1 },
      { ago: 3, mastery: 63, voice: 3, low: 1, passed: 1 },
      { ago: 1, mastery: 71.7, voice: 4, low: 3, passed: 0 },
    ],
    nodes: {
      "ENG5-U11-VOCAB": {
        m: 84,
        conf: 68,
        passed: true,
        status: "PASSED",
        items: 6,
        solved: 6,
        attempts: 7,
        hints: 1,
        seconds: 34,
      },
      "ENG5-U11-PAST": {
        m: 77,
        conf: 61,
        passed: true,
        status: "PASSED",
        items: 7,
        solved: 6,
        attempts: 9,
        hints: 3,
        seconds: 41,
        mis: [{ id: "ENG5-U11-M05", count: 1, status: "RESOLVED" }],
      },
      "ENG5-U11-DIDYOU": {
        m: 54,
        conf: 42,
        passed: false,
        status: "CURRENT",
        items: 5,
        solved: 3,
        attempts: 8,
        hints: 4,
        seconds: 52,
        mis: [{ id: "ENG5-U11-M03", count: 2, status: "ACTIVE" }],
      },
      "ENG5-U11-WHATDID": { ...off, status: "AVAILABLE" },
      "ENG5-U11-STRESS": off,
      "ENG5-U11-TRIP": off,
    },
  },
  {
    student_id: "demo-lan",
    display_name: "Lan",
    parent_code: "D4E5F6",
    step: 3,
    sessions: { total: 5, completed: 4, unfinished: 1, minutes: 76 },
    voiceShare: 30,
    days: [
      { ago: 11, mastery: 31, voice: 1, low: 0, passed: 1 },
      { ago: 8, mastery: 55, voice: 2, low: 0, passed: 1 },
      { ago: 5, mastery: 64, voice: 2, low: 0, passed: 1 },
      { ago: 2, mastery: 71.8, voice: 2, low: 1, passed: 0 },
    ],
    nodes: {
      "ENG5-U11-VOCAB": {
        m: 88,
        conf: 72,
        passed: true,
        status: "PASSED",
        items: 6,
        solved: 6,
        attempts: 6,
        hints: 0,
        seconds: 29,
      },
      "ENG5-U11-PAST": {
        m: 79,
        conf: 63,
        passed: true,
        status: "PASSED",
        items: 7,
        solved: 6,
        attempts: 8,
        hints: 2,
        seconds: 38,
      },
      "ENG5-U11-DIDYOU": {
        m: 76,
        conf: 58,
        passed: true,
        status: "PASSED",
        items: 6,
        solved: 5,
        attempts: 8,
        hints: 2,
        seconds: 44,
      },
      "ENG5-U11-WHATDID": {
        m: 44,
        conf: 39,
        passed: false,
        status: "CURRENT",
        items: 5,
        solved: 2,
        attempts: 9,
        hints: 5,
        seconds: 61,
        mis: [{ id: "ENG5-U11-M07", count: 3, status: "ACTIVE" }],
      },
      "ENG5-U11-STRESS": off,
      "ENG5-U11-TRIP": off,
    },
  },
  {
    student_id: "demo-minh",
    display_name: "Minh",
    parent_code: "G7H8J9",
    step: 2,
    sessions: { total: 6, completed: 5, unfinished: 1, minutes: 94 },
    voiceShare: 40,
    days: [
      { ago: 12, mastery: 40, voice: 2, low: 0, passed: 1 },
      { ago: 9, mastery: 61, voice: 3, low: 0, passed: 1 },
      { ago: 6, mastery: 70, voice: 2, low: 0, passed: 1 },
      { ago: 4, mastery: 74, voice: 3, low: 1, passed: 1 },
      { ago: 0, mastery: 70.2, voice: 2, low: 0, passed: 0 },
    ],
    nodes: {
      "ENG5-U11-VOCAB": {
        m: 93,
        conf: 78,
        passed: true,
        status: "PASSED",
        items: 6,
        solved: 6,
        attempts: 6,
        hints: 0,
        seconds: 25,
      },
      "ENG5-U11-PAST": {
        m: 86,
        conf: 70,
        passed: true,
        status: "PASSED",
        items: 7,
        solved: 7,
        attempts: 8,
        hints: 1,
        seconds: 31,
      },
      "ENG5-U11-DIDYOU": {
        m: 82,
        conf: 66,
        passed: true,
        status: "PASSED",
        items: 6,
        solved: 6,
        attempts: 7,
        hints: 1,
        seconds: 35,
      },
      "ENG5-U11-WHATDID": {
        m: 79,
        conf: 60,
        passed: true,
        status: "PASSED",
        items: 7,
        solved: 6,
        attempts: 9,
        hints: 2,
        seconds: 40,
        mis: [{ id: "ENG5-U11-M08", count: 1, status: "RESOLVED" }],
      },
      "ENG5-U11-STRESS": {
        m: 63,
        conf: 44,
        passed: false,
        status: "CURRENT",
        items: 4,
        solved: 3,
        attempts: 5,
        hints: 2,
        seconds: 33,
      },
      "ENG5-U11-TRIP": {
        m: 18,
        conf: 22,
        passed: false,
        status: "AVAILABLE",
        items: 1,
        solved: 0,
        attempts: 2,
        hints: 1,
        seconds: 70,
      },
    },
  },
];

/** The demo student who learns in the browser: the student's own pages show this one. */
export const ME = DEMO_STUDENTS[0];

/** Dimensions that have evidence on a node: application and transfer only where the unit has items. */
const HAS: Record<string, Dimension[]> = {
  "ENG5-U11-VOCAB": ["C", "R", "I", "D"],
  "ENG5-U11-PAST": ["C", "R", "I", "D"],
  "ENG5-U11-DIDYOU": ["C", "R", "A", "T", "I", "D"],
  "ENG5-U11-WHATDID": ["C", "R", "A", "T", "I", "D"],
  "ENG5-U11-STRESS": ["C", "R", "I"],
  "ENG5-U11-TRIP": ["C", "R", "A", "T", "I"],
};
const SHIFT: Record<Dimension, number> = { C: 7, R: -5, A: -3, T: -10, I: -8, S: 0, D: 2 };
const EVIDENCE: Record<Dimension, number> = { C: 0.8, R: 0.3, A: 0.25, T: 0.12, I: 0.6, S: 0, D: 0.2 };

const clamp = (v: number) => Math.max(0, Math.min(100, Math.round(v * 10) / 10));
const round1 = (v: number) => Math.round(v * 10) / 10;

function level(m: number | null): number {
  if (m === null) return 0;
  if (m < 20) return 0;
  if (m < 40) return 1;
  if (m < 60) return 2;
  if (m < 75) return 3;
  return 4; // S stays empty, so no PROVISIONALLY_MASTERED yet (ADR-060 §4)
}

function insufficient(n: DemoNode): boolean {
  return n.m !== null && n.conf < 30 && !n.passed; // DI-7
}

/** DI-113: one table for both subjects. */
function quality(n: DemoNode): Quality {
  if (n.m === null) return "NOT_STARTED";
  if (insufficient(n)) return "INSUFFICIENT_DATA";
  const l = level(n.m);
  if (l <= 1) return "FAMILIAR";
  if (l === 2) return "WITH_SUPPORT";
  if (l <= 4) return "INDEPENDENT";
  return "SOLID";
}

/** DI-27. */
function group(n: DemoNode): KcGroup {
  if (n.passed) return "PASSED";
  if (n.m === null) return "NOT_STARTED";
  if (insufficient(n)) return "INSUFFICIENT";
  return n.m < 60 ? "WEAK" : "UNSTABLE";
}

/** DI-8, with ADR-060 §8: an open CRITICAL misconception asks for a diagnosis first. */
function recommendation(nodeId: string, n: DemoNode): Recommendation {
  const critical = (n.mis ?? []).some(
    (x) => x.status !== "RESOLVED" && MISCONCEPTIONS.find((m) => m.id === x.id)?.severity === "CRITICAL",
  );
  if (critical || n.m === null) return "DIAGNOSE";
  if (n.m < 40) return "EXPLAIN";
  if (n.m < 60) return "GUIDED";
  if (n.m < 75) return "PRACTICE";
  if (n.m < 90) return nodeId === "ENG5-U11-TRIP" ? "CHALLENGE" : "TRANSFER";
  return "CHALLENGE";
}

function nodeDimensions(nodeId: string, n: DemoNode): TeacherNodeDetail["dimensions"] {
  const has = HAS[nodeId] ?? [];
  return Object.fromEntries(
    DIMENSIONS.map((d) => {
      if (n.m === null || !has.includes(d)) return [d, { value: 0, n_eff: 0, in_mastery: false }];
      const n_eff = round1((n.items ?? 0) * EVIDENCE[d] + (d === "R" ? 0.4 : 0));
      return [d, { value: clamp(n.m + SHIFT[d]), n_eff, in_mastery: n_eff >= 1 }];
    }),
  ) as TeacherNodeDetail["dimensions"];
}

function isoDay(now: Date, ago: number): string {
  const d = new Date(now.getTime() - ago * 86_400_000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function at(now: Date, ago: number, hour = 19): string {
  const d = new Date(now.getTime() - ago * 86_400_000);
  d.setHours(hour, 15, 0, 0);
  return d.toISOString();
}

function misName(id: string): string {
  return MISCONCEPTIONS.find((m) => m.id === id)?.name ?? id;
}

function overall(s: DemoStudent) {
  const scored = NODES.map((n) => s.nodes[n.node_id]).filter((n) => n.m !== null);
  const mastery = scored.length ? round1(scored.reduce((a, n) => a + (n.m ?? 0), 0) / scored.length) : null;
  const confidence = scored.length ? round1(scored.reduce((a, n) => a + n.conf, 0) / scored.length) : null;
  return {
    mastery,
    confidence,
    level: mastery === null ? null : level(mastery),
    coverage: round1((100 * scored.length) / NODES.length),
    passed: NODES.filter((n) => s.nodes[n.node_id].passed).length,
    total: NODES.length,
  };
}

/** The spoken turns of the demo student (DI-114): verbatim transcripts, q, the language asked. */
function voiceTurns(s: DemoStudent, now: Date): VoiceTurn[] {
  if (s !== ME) {
    return [
      {
        turn_id: `${s.student_id}-v1`,
        session_id: `${s.student_id}-s1`,
        at: at(now, s.days.at(-1)?.ago ?? 0, 19),
        node_id: "ENG5-U11-WHATDID",
        item_id: "U11-WD-PR-01",
        prompt: "What did your family do in Nha Trang?",
        transcript: s.display_name === "Lan" ? "We eat seafood." : "We ate seafood.",
        asr_confidence: 0.84,
        language: "en",
        audio_ref: `${s.student_id}-v1`,
        outcome: s.display_name === "Lan" ? "WRONG" : "CORRECT",
      },
    ];
  }
  const turn = (
    i: number,
    ago: number,
    node: string,
    item: string | null,
    prompt: string,
    transcript: string,
    q: number | null,
    language: "en" | "vi",
    outcome: VoiceTurn["outcome"],
    extra: Partial<VoiceTurn> = {},
  ): VoiceTurn => ({
    turn_id: `an-v${i}`,
    session_id: ago <= 1 ? "eng-demo-an-4" : "eng-demo-an-3",
    at: at(now, ago, 19 + (i % 2)),
    node_id: node,
    item_id: item,
    prompt,
    transcript,
    asr_confidence: q,
    language,
    audio_ref: `an-v${i}`,
    outcome,
    ...extra,
  });
  const DY = "ENG5-U11-DIDYOU";
  return [
    turn(
      8,
      1,
      DY,
      "U11-DY-PR-02",
      "Con hỏi bạn đã nhặt vỏ sò chưa, bằng câu “Did you …?”.",
      "Did you collect seashells?",
      0.88,
      "en",
      "CORRECT",
    ),
    turn(
      7,
      1,
      DY,
      "U11-DY-PR-01",
      "Bạn hỏi: “Did you take photos?” Câu trả lời nào đúng?",
      "Yes I do",
      0.52,
      "en",
      "WRONG",
    ),
    turn(6, 1, DY, null, "Vì sao con trả lời bằng did?", "vì bạn hỏi bằng did ạ", 0.72, "vi", "CORRECT"),
    turn(
      5,
      1,
      DY,
      "U11-DY-CP-01",
      "Con nói theo cô: Yes, I did. I swam with my mother.",
      "Yes I did I swim with my mother",
      0.41,
      "en",
      null,
    ),
    turn(
      4,
      3,
      DY,
      "U11-DY-CC-01",
      "Con chọn từ đúng: Did you (walk / walked) on the beach?",
      "walk",
      0.57,
      "en",
      "CORRECT",
      {
        teacher_override: true,
      },
    ),
    turn(
      3,
      3,
      "ENG5-U11-PAST",
      "U11-PA-PR-01",
      "I (swim / swam) with my father yesterday.",
      "swam",
      0.93,
      "en",
      "CORRECT",
    ),
    turn(
      2,
      3,
      "ENG5-U11-PAST",
      "U11-PA-PR-02",
      "Đổi sang chuyện hôm qua: Today we buy souvenirs.",
      "Yesterday we bought souvenirs.",
      0.86,
      "en",
      "CORRECT",
    ),
    turn(
      1,
      6,
      "ENG5-U11-VOCAB",
      "U11-VO-CP-01",
      "Con nói theo cô: We took a boat trip around the bay.",
      "We took a boat trip around the bay",
      0.9,
      "en",
      null,
    ),
  ];
}

function sessionList(s: DemoStudent, now: Date): ParentChildView["session_list"] {
  return s.days
    .slice(-4)
    .map((d, i, all) => ({
      session_id: `eng-${s.student_id}-${i + 1}`,
      started_at: at(now, d.ago, 19),
      minutes: 12 + ((i * 5) % 9),
      lifecycle_state: i === all.length - 1 ? ("ACTIVE" as const) : ("COMPLETED" as const),
      passed_names: d.passed
        ? NODES.filter((n) => s.nodes[n.node_id].passed)
            .slice(i, i + 1)
            .map((n) => n.name)
        : [],
    }))
    .reverse();
}

function attention(s: DemoStudent, now: Date): AttentionReason[] {
  const reasons: AttentionReason[] = [];
  for (const node of NODES) {
    for (const m of s.nodes[node.node_id].mis ?? []) {
      if (m.status !== "RESOLVED" && m.count >= 2) {
        reasons.push({
          kind: "MISCONCEPTION",
          node_id: node.node_id,
          misconception_id: m.id,
          count: m.count,
        });
      }
    }
  }
  // DI-114: ≥ 40% of the spoken turns of the last 7 days with q < 0,6, and at least 5 turns.
  const week = s.days.filter((d) => d.ago <= 7);
  const turns = week.reduce((a, d) => a + d.voice, 0);
  const low = week.reduce((a, d) => a + d.low, 0);
  if (turns >= 5 && low / turns >= 0.4) {
    reasons.push({ kind: "ASR_LOW", voice_turns: turns, share: Math.round((100 * low) / turns) / 100 });
  }
  void now;
  return reasons;
}

function progressNodes(s: DemoStudent): ProgressNode[] {
  return NODES.map((n) => {
    const d = s.nodes[n.node_id];
    return {
      node_id: n.node_id,
      name: n.name,
      layer: n.layer,
      status: d.status,
      level: d.m === null ? null : level(d.m),
      quality: quality(d),
      order: n.order,
      passed: d.passed,
      pattern: n.pattern,
    };
  });
}

function topics(s: DemoStudent) {
  const nodes = progressNodes(s);
  const going_well: ProgressTopic[] = nodes
    .filter((n) => n.quality === "INDEPENDENT" || n.quality === "SOLID")
    .map((n) => ({ node_id: n.node_id, name: n.name, quality: n.quality, pattern: n.pattern }));
  const to_practise: ProgressTopic[] = [];
  for (const n of NODES) {
    const d = s.nodes[n.node_id];
    const open = (d.mis ?? []).find((m) => m.status !== "RESOLVED");
    const q = quality(d);
    if (open || q === "FAMILIAR" || q === "WITH_SUPPORT") {
      to_practise.push({
        node_id: n.node_id,
        name: n.name,
        quality: q,
        pattern: n.pattern,
        reason: open
          ? (MISCONCEPTIONS.find((m) => m.id === open.id)?.parent ?? null)
          : "Con làm được khi có gợi ý của cô; mình ôn thêm để con tự nói được.",
      });
    }
  }
  return { going_well, to_practise };
}

export function studentOverview(s: DemoStudent, now: Date): StudentOverview {
  const o = overall(s);
  const week = s.days.filter((d) => d.ago <= (now.getDay() + 6) % 7);
  return {
    student_display_name: s.display_name,
    parent_code: s.parent_code,
    chapter: { ...UNIT, subject: "english" },
    chapters: [{ ...UNIT, subject: "english" }],
    nodes: progressNodes(s),
    relations: RELATIONS,
    passed: o.passed,
    total: o.total,
    sessions: s.sessions,
    study_days: s.days.map((d) => isoDay(now, d.ago)),
    streak: s.days.some((d) => d.ago <= 1) ? 1 : 0,
    this_week: { study_days: week.length, passed: week.reduce((a, d) => a + d.passed, 0) },
    ...topics(s),
    current_session_id: null,
    last_session_at: at(now, s.days.at(-1)?.ago ?? 0),
    current_step: s.step,
  };
}

export function parentView(s: DemoStudent, now: Date): ParentChildView {
  const studied = new Map(s.days.map((d) => [isoDay(now, d.ago), d]));
  let passed = 0;
  let started = 0;
  const trend = Array.from({ length: 28 }, (_, i) => {
    const date = isoDay(now, 27 - i);
    const day = studied.get(date);
    if (day) {
      passed += day.passed;
      started = Math.min(NODES.length, started + 1);
    }
    return { date, studied: Boolean(day), passed, started };
  });
  return {
    ...studentOverview(s, now),
    trend,
    home_tips: NODES.filter((n) => s.nodes[n.node_id].status !== "LOCKED").map((n) => ({
      node_id: n.node_id,
      name: n.name,
      tip: n.home_tip,
      example: n.example,
    })),
    session_list: sessionList(s, now),
  };
}

function cell(nodeId: string, n: DemoNode): MasteryCell {
  return {
    node_id: nodeId,
    mastery: n.m,
    confidence: n.conf,
    level: level(n.m),
    state: STATES[level(n.m)],
    insufficient_data: insufficient(n),
    passed: n.passed,
    status: n.status,
    active_misconceptions: (n.mis ?? []).filter((m) => m.status !== "RESOLVED").length,
  };
}

const TEACHER_NODES = NODES.map((n) => ({
  node_id: n.node_id,
  name: n.name,
  layer: n.layer,
  order: n.order,
  min_mastery: MIN_MASTERY,
}));

export function classOverview(now: Date): ClassOverview {
  const students: ClassStudent[] = DEMO_STUDENTS.map((s) => {
    const o = overall(s);
    return {
      student_id: s.student_id,
      display_name: s.display_name,
      sessions: s.sessions,
      last_active_at: at(now, s.days.at(-1)?.ago ?? 0),
      passed: o.passed,
      overall: { mastery: o.mastery, confidence: o.confidence, level: o.level, coverage: o.coverage },
      cells: NODES.map((n) => cell(n.node_id, s.nodes[n.node_id])),
      attention: attention(s, now),
    };
  });
  const by_node = NODES.map((n) => {
    const scored = DEMO_STUDENTS.map((s) => s.nodes[n.node_id]).filter((d) => d.m !== null);
    return {
      node_id: n.node_id,
      mean_mastery: scored.length ? round1(scored.reduce((a, d) => a + (d.m ?? 0), 0) / scored.length) : null,
      students: scored.length,
      passed: DEMO_STUDENTS.filter((s) => s.nodes[n.node_id].passed).length,
    };
  });
  const found = new Map<string, { count: number; students: number; active: number }>();
  for (const s of DEMO_STUDENTS) {
    for (const node of NODES) {
      for (const m of s.nodes[node.node_id].mis ?? []) {
        const f = found.get(m.id) ?? { count: 0, students: 0, active: 0 };
        f.count += m.count;
        f.students += 1;
        if (m.status !== "RESOLVED") f.active += 1;
        found.set(m.id, f);
      }
    }
  }
  const totalFound = [...found.values()].reduce((a, f) => a + f.count, 0);
  const misconceptions: ClassMisconception[] = [...found.entries()]
    .map(([id, f]) => {
      const m = MISCONCEPTIONS.find((x) => x.id === id);
      return {
        id,
        name: misName(id),
        node_id: m?.node_id ?? null,
        severity: m?.severity ?? "NORMAL",
        count: f.count,
        share: round1((100 * f.count) / totalFound),
        students: f.students,
        active_students: f.active,
        recent: f.active ? f.count : 0,
      };
    })
    .sort((a, b) => b.count - a.count);
  const means = students.map((s) => s.overall.mastery).filter((m): m is number => m !== null);
  return {
    chapter: { ...UNIT },
    nodes: TEACHER_NODES,
    students,
    by_node,
    misconceptions,
    kpis: {
      students: students.length,
      active_this_week: DEMO_STUDENTS.filter((s) => s.days.some((d) => d.ago <= 6)).length,
      sessions: DEMO_STUDENTS.reduce((a, s) => a + s.sessions.total, 0),
      minutes: DEMO_STUDENTS.reduce((a, s) => a + s.sessions.minutes, 0),
      passed: students.reduce((a, s) => a + s.passed, 0),
      cells: students.length * NODES.length,
      mean_mastery: means.length ? round1(means.reduce((a, m) => a + m, 0) / means.length) : null,
      attention: students.filter((s) => s.attention.length > 0).length,
      voice_share: Math.round(DEMO_STUDENTS.reduce((a, s) => a + s.voiceShare, 0) / DEMO_STUDENTS.length),
    },
  };
}

function journey(s: DemoStudent, now: Date): JourneyStep[] {
  const steps: JourneyStep[] = [];
  const pattern: JourneyStep["resolution"][] = [
    "WORKED",
    "SUPPORTED",
    "SUPPORTED",
    "INDEPENDENT",
    "INDEPENDENT",
    "INDEPENDENT",
    "INDEPENDENT",
  ];
  NODES.forEach((n, ni) => {
    const d = s.nodes[n.node_id];
    for (let i = 0; i < (d.items ?? 0); i += 1) {
      const resolution: JourneyStep["resolution"] = d.passed
        ? (pattern[Math.min(i + ni, pattern.length - 1)] ?? "INDEPENDENT")
        : (["WORKED", "UNRESOLVED", "SUPPORTED", "INDEPENDENT", "SUPPORTED"][i] as JourneyStep["resolution"]);
      steps.push({
        node_id: n.node_id,
        item_id: `${n.node_id.replace("ENG5-", "")}-${i + 1}`,
        modality: i % 2 === 1 ? "VOICE" : "TEXT",
        resolution,
        attempts: resolution === "INDEPENDENT" ? 1 : 2,
        hints: resolution === "SUPPORTED" ? 2 : resolution === "WORKED" ? 4 : 0,
        at: at(now, s.days[Math.min(ni, s.days.length - 1)]?.ago ?? 0),
      });
    }
  });
  return steps;
}

export function studentReport(studentId: string, now: Date): TeacherStudentView | null {
  const s = DEMO_STUDENTS.find((x) => x.student_id === studentId);
  if (!s) return null;
  const o = overall(s);
  const nodes: TeacherNodeDetail[] = NODES.map((n, i) => {
    const d = s.nodes[n.node_id];
    const trend =
      d.m === null
        ? []
        : [d.m - 24, d.m - 15, d.m - 9, d.m - 3, d.m].map((m, k) => ({
            at: at(now, (s.days[Math.min(i, s.days.length - 1)]?.ago ?? 0) + 4 - k),
            mastery: clamp(m),
          }));
    return {
      ...TEACHER_NODES[i],
      ...cell(n.node_id, d),
      group: group(d),
      dimensions: nodeDimensions(n.node_id, d),
      items: d.items ?? 0,
      solved: d.solved ?? 0,
      attempts: d.attempts ?? 0,
      hints: d.hints ?? 0,
      seconds: d.seconds ?? null,
      misconceptions: (d.mis ?? []).map((m) => ({
        id: m.id,
        name: misName(m.id),
        severity: MISCONCEPTIONS.find((x) => x.id === m.id)?.severity ?? "NORMAL",
        count: m.count,
        status: m.status,
      })),
      trend,
      direction: d.m === null ? null : "UP",
      recommendation: recommendation(n.node_id, d),
    };
  });
  const dimensions = Object.fromEntries(
    DIMENSIONS.map((dim) => {
      const counted = nodes.filter((n) => n.dimensions[dim].in_mastery);
      const n_eff = round1(counted.reduce((a, n) => a + n.dimensions[dim].n_eff, 0));
      if (counted.length === 0) return [dim, { value: null, n_eff }];
      const value =
        counted.reduce((a, n) => a + n.dimensions[dim].value * n.dimensions[dim].n_eff, 0) / n_eff;
      return [dim, { value: round1(value), n_eff }];
    }),
  ) as TeacherStudentView["dimensions"];
  const strengths = DIMENSIONS.filter((d) => (dimensions[d].value ?? -1) >= 75);
  const weaknesses = DIMENSIONS.filter(
    (d) => dimensions[d].value !== null && (dimensions[d].value ?? 0) < 60,
  );
  const timeline = s.days.map((d) => ({ date: isoDay(now, d.ago), mastery: d.mastery }));
  const before = s.days.filter((d) => d.ago > 6).at(-1);
  return {
    student_id: s.student_id,
    display_name: s.display_name,
    chapter: { ...UNIT },
    relations: RELATIONS,
    sessions: s.sessions,
    session_list: sessionList(s, now),
    last_active_at: at(now, s.days.at(-1)?.ago ?? 0),
    overall: o,
    dimensions,
    strengths,
    weaknesses,
    nodes,
    timeline,
    velocity:
      before && o.mastery !== null
        ? { change: round1(o.mastery - before.mastery), since: isoDay(now, before.ago) }
        : null,
    activity: s.days.map((d, i) => ({
      date: isoDay(now, d.ago),
      independent: 2 + (i % 3),
      supported: 1 + (i % 2),
      worked: i === 0 ? 2 : 1,
      unresolved: i === s.days.length - 1 ? 1 : 0,
      hints: 2 + i,
      passed: d.passed,
      voice_turns: d.voice,
      asr_low: d.low,
    })),
    attention: attention(s, now),
    journey: journey(s, now),
    voice_turns: voiceTurns(s, now),
  };
}
