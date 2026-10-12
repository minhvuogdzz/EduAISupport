import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";

import { useApi } from "../../api/apiContext";
import { DEMO_STUDENT_NAME } from "../../api/http/httpApi";
import type { SessionSummary, StudentOverview } from "../../api/contract";
import { AppShell } from "../../components/AppShell";
import { useAuth } from "../auth/authContext";
import {
  ArrowRightIcon,
  BookIcon,
  CheckIcon,
  ClockIcon,
  FlameIcon,
  HeartIcon,
  SparklesIcon,
} from "../../components/icons";
import { LIFECYCLE_LABEL, minutesText, QUALITY_TONE, studentWords } from "../../components/labels";
import { Mascot } from "../../components/Mascot";
import { formatViDateTime } from "../../lib/viNumber";
import { KnowledgeMap } from "../teaching/KnowledgeMap";
import { readLastSessionId, rememberSession } from "./lastSession";

const WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];

/**
 * The student's home: a greeting, how the chapter is going (in words, never scores: PART 27.1), what
 * to practise, the week, the code for the parent and every past session. A given name starts a session
 * (temporary demo identity, until T12 adds class code + PIN).
 */
export function StudentStartPage() {
  const api = useApi();
  const navigate = useNavigate();
  const [lastSessionId] = useState(readLastSessionId);

  const last = useQuery({
    queryKey: ["session-state", lastSessionId],
    queryFn: () => api.getState(lastSessionId ?? ""),
    enabled: lastSessionId !== null,
    retry: false,
  });
  const resumable = last.data && last.data.lifecycle_state !== "COMPLETED" ? last.data : null;
  // Every session of this student is kept with its whole conversation (the real API stores them).
  const history = useQuery({ queryKey: ["my-sessions"], queryFn: () => api.listMySessions(), retry: false });
  const overview = useQuery({
    queryKey: ["my-overview"],
    queryFn: () => api.getMyOverview!(),
    enabled: api.getMyOverview !== undefined,
    retry: false,
  });
  const { user } = useAuth();
  // The trial has one student (ACC-1, ACC-2): the account's name, else the demo student's. Never typed.
  const name = user?.display_name || overview.data?.student_display_name || DEMO_STUDENT_NAME;

  const start = useMutation({
    mutationFn: (studentName: string) => api.createDemoSession({ student_display_name: studentName }),
    onSuccess: ({ session_id }) => {
      rememberSession(session_id);
      void navigate(`/student/sessions/${session_id}`);
    },
  });

  return (
    <AppShell>
      <title>Học sinh · CAVAT</title>
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8">
        <section className="card brand-gradient overflow-hidden">
          <div className="grid items-center gap-4 p-6 md:grid-cols-[1fr_auto] md:p-8">
            <div>
              <h1 className="text-2xl font-extrabold md:text-3xl">
                {`Chào ${name}, hôm nay mình học gì nhé?`}
              </h1>
              <p className="mt-2 text-base text-slate-700">
                {overview.data
                  ? `Chương ${overview.data.chapter.title}: con đã qua ${overview.data.passed}/${overview.data.total} bài.`
                  : "Cô sẵn sàng học cùng con rồi!"}
              </p>
              {resumable && (
                <div className="mt-4 rounded-2xl bg-white/80 p-4 ring-1 ring-gold/40">
                  <p className="text-lg">
                    Buổi học của <strong>{resumable.student_display_name}</strong> còn dang dở (đã xong{" "}
                    {resumable.progress.items_done}/{resumable.progress.items_total}{" "}
                    {resumable.teaching ? "bài" : "câu"}).
                  </p>
                  <Link
                    to={`/student/sessions/${resumable.session_id}`}
                    className="mt-3 inline-flex items-center gap-2 rounded-full bg-brand-700 px-5 py-2.5 text-lg font-semibold text-white hover:bg-brand-800"
                  >
                    Học tiếp
                  </Link>
                </div>
              )}
              <StartForm
                knownName={name}
                pending={start.isPending}
                failed={start.isError}
                onStart={(studentName) => start.mutate(studentName)}
              />
            </div>
            <Mascot
              mood={overview.data?.passed ? "celebrating" : "happy"}
              size={150}
              className="justify-self-center"
            />
          </div>
        </section>

        {overview.data && <Dashboard overview={overview.data} />}
        {history.data && history.data.length > 0 && <SessionHistory sessions={history.data} />}
      </div>
    </AppShell>
  );
}

function StartForm({
  knownName,
  pending,
  failed,
  onStart,
}: {
  knownName: string;
  pending: boolean;
  failed: boolean;
  onStart: (name: string) => void;
}) {
  return (
    <div className="mt-5 flex flex-wrap gap-3">
      <button
        type="button"
        disabled={pending}
        onClick={() => onStart(knownName)}
        className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-lg font-semibold text-brand-900 ring-1 ring-brand-200 hover:bg-brand-50 disabled:opacity-50"
      >
        Bắt đầu buổi mới <ArrowRightIcon className="size-5" />
      </button>
      {failed && (
        <p role="alert" className="text-lg text-red-700">
          Chưa tạo được buổi học. Con thử lại nhé.
        </p>
      )}
    </div>
  );
}

function Dashboard({ overview }: { overview: StudentOverview }) {
  const nodes = overview.nodes.map((n) => ({ ...n }));
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          icon={<FlameIcon className="size-5 text-orange-500" />}
          label="Chuỗi ngày học"
          value={`${overview.streak} ngày`}
        />
        <Stat
          icon={<CheckIcon className="size-5 text-emerald-600" />}
          label="Bài đã qua"
          value={`${overview.passed}/${overview.total}`}
        />
        <Stat
          icon={<ClockIcon className="size-5 text-brand-700" />}
          label="Thời gian học"
          value={minutesText(overview.sessions.minutes, overview.sessions.total)}
        />
        <Stat
          icon={<BookIcon className="size-5 text-sky-700" />}
          label="Buổi học"
          value={`${overview.sessions.total}`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <section aria-labelledby="map-title" className="card p-6">
          <h2 id="map-title" className="text-xl font-bold">
            Bản đồ chương {overview.chapter.title}
          </h2>
          <p className="mb-4 text-slate-600">Học từ trên xuống: bài trên là nền của bài dưới.</p>
          <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,26rem)_1fr]">
            <KnowledgeMap
              nodes={nodes}
              relations={overview.relations}
              title={`Bản đồ chương ${overview.chapter.title}`}
            />
            <ul className="flex flex-col gap-2">
              {overview.nodes.map((node) => (
                <li
                  key={node.node_id}
                  className="flex items-center justify-between gap-3 rounded-2xl bg-slate-50 px-3 py-2"
                >
                  <span className="font-medium">{node.name}</span>
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-0.5 text-sm font-semibold ring-1 ${
                      node.quality === "NOT_STARTED" && node.status === "CURRENT"
                        ? "bg-brand-50 text-brand-900 ring-brand-200"
                        : QUALITY_TONE[node.quality]
                    }`}
                  >
                    {studentWords(node.quality, node.status)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <div className="flex flex-col gap-6">
          <section
            aria-labelledby="practise-title"
            className="rounded-3xl border border-amber-200 bg-amber-50 p-6"
          >
            <h2 id="practise-title" className="text-lg font-bold text-amber-900">
              Cần luyện thêm
            </h2>
            {overview.to_practise.length === 0 ? (
              <p className="mt-2 text-amber-950/80">Chưa có gì cần ôn. Con cứ học tiếp nhé!</p>
            ) : (
              <ul className="mt-2 flex flex-col gap-3">
                {overview.to_practise.map((topic) => (
                  <li key={topic.node_id}>
                    <p className="text-lg font-semibold text-amber-950">{topic.name}</p>
                    <p className="text-amber-950/80">{topic.reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section
            aria-labelledby="well-title"
            className="rounded-3xl border border-emerald-200 bg-emerald-50 p-6"
          >
            <h2 id="well-title" className="text-lg font-bold text-emerald-900">
              Con đã làm tốt
            </h2>
            {overview.going_well.length === 0 ? (
              <p className="mt-2 text-emerald-950/80">Học xong bài đầu tiên là có ngay mục này!</p>
            ) : (
              <ul className="mt-2 flex flex-col gap-2">
                {overview.going_well.map((topic) => (
                  <li
                    key={topic.node_id}
                    className="flex items-center gap-2 text-lg font-semibold text-emerald-950"
                  >
                    <SparklesIcon className="size-5 shrink-0 text-emerald-600" />
                    {topic.name}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <WeekCard overview={overview} />
          <ParentCode code={overview.parent_code} />
        </div>
      </div>
    </>
  );
}

function Stat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="card flex items-center gap-4 p-5">
      <span className="flex size-11 items-center justify-center rounded-2xl bg-slate-50">{icon}</span>
      <span>
        <span className="block text-sm text-slate-600">{label}</span>
        <span className="block text-2xl font-bold">{value}</span>
      </span>
    </div>
  );
}

/** This week, Monday to Sunday: the days the student learned. Encouraging, never a penalty. */
function WeekCard({ overview }: { overview: StudentOverview }) {
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  const studied = new Set(overview.study_days);
  const days = WEEKDAYS.map((label, i) => {
    const day = new Date(monday);
    day.setDate(monday.getDate() + i);
    const iso = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
    return { label, iso, studied: studied.has(iso) };
  });
  return (
    <section aria-labelledby="week-title" className="card p-6">
      <h2 id="week-title" className="text-lg font-bold">
        Tuần này
      </h2>
      <ol className="mt-3 grid grid-cols-7 gap-1.5">
        {days.map((day) => (
          <li key={day.iso} className="flex flex-col items-center gap-1 text-sm text-slate-600">
            <span
              className={`flex size-9 items-center justify-center rounded-full ${
                day.studied ? "bg-orange-100 text-orange-600" : "bg-slate-100 text-slate-400"
              }`}
            >
              {day.studied ? <FlameIcon className="size-5" /> : "·"}
            </span>
            {day.label}
            <span className="sr-only">{day.studied ? "có học" : "chưa học"}</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-slate-700">
        Tuần này con học {overview.this_week.study_days} ngày
        {overview.this_week.passed > 0 ? ` và qua ${overview.this_week.passed} bài` : ""}.
      </p>
    </section>
  );
}

function ParentCode({ code }: { code: string }) {
  return (
    <section aria-labelledby="code-title" className="card p-6">
      <h2 id="code-title" className="flex items-center gap-2 text-lg font-bold">
        <HeartIcon className="size-5 text-rose-500" /> Mã cho bố mẹ
      </h2>
      <p className="mt-1 text-slate-600">Đưa mã này cho bố mẹ để xem con học thế nào.</p>
      <p className="mt-3 font-mono text-3xl font-bold tracking-[0.3em] text-brand-900">{code}</p>
      <Link to={`/parent/${code}`} className="mt-2 inline-block text-brand-800 underline">
        Mở trang phụ huynh
      </Link>
    </section>
  );
}

/** "Lịch sử học": every session of this student, newest first; each opens with its whole conversation. */
function SessionHistory({ sessions }: { sessions: SessionSummary[] }) {
  return (
    <section aria-labelledby="history-title" className="card flex flex-col gap-3 p-6">
      <h2 id="history-title" className="text-2xl font-bold">
        Lịch sử học
      </h2>
      <ol className="flex flex-col divide-y divide-slate-100">
        {sessions.map((session) => {
          const done = session.lifecycle_state === "COMPLETED";
          const unit = session.mode === "CHAPTER" ? "bài đã qua" : "câu";
          const when = session.started_at ? formatViDateTime(session.started_at) : "chưa bắt đầu";
          return (
            <li key={session.session_id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="flex flex-col">
                <span className="text-xl font-medium">{session.lesson_title}</span>
                <span className="text-base text-slate-600">
                  {when} · {session.progress.items_done}/{session.progress.items_total} {unit} ·{" "}
                  {LIFECYCLE_LABEL[session.lifecycle_state]}
                </span>
              </div>
              <Link
                to={`/student/sessions/${session.session_id}`}
                aria-label={`${done ? "Xem lại" : "Học tiếp"} buổi ${session.lesson_title} lúc ${when}`}
                className={`rounded-full px-5 py-2 text-lg font-semibold ${
                  done ? "bg-white text-brand-800 ring-2 ring-brand-700" : "bg-brand-700 text-white"
                }`}
              >
                {done ? "Xem lại" : "Học tiếp"}
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
