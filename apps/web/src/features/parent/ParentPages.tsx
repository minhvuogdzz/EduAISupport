import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { useApi } from "../../api/apiContext";
import { ApiError } from "../../api/client";
import type { ParentChildView, Quality } from "../../api/contract";
import { AppShell } from "../../components/AppShell";
import {
  BookIcon,
  CheckIcon,
  ClockIcon,
  FlameIcon,
  HeartIcon,
  SparklesIcon,
  TargetIcon,
} from "../../components/icons";
import {
  LIFECYCLE_LABEL,
  minutesText,
  QUALITY_LABEL,
  QUALITY_MEANING,
  QUALITY_TONE,
  topicState,
} from "../../components/labels";
import { Mascot } from "../../components/Mascot";
import { formatViDateTime } from "../../lib/viNumber";
import { ProgressTrend } from "./ProgressTrend";

const QUALITY_ORDER: Quality[] = [
  "SOLID",
  "INDEPENDENT",
  "WITH_SUPPORT",
  "FAMILIAR",
  "INSUFFICIENT_DATA",
  "NOT_STARTED",
];

/** The parent's entry: the child's code (shown on the child's page) opens the child's progress. */
export function ParentPage() {
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  return (
    <AppShell>
      <title>Phụ huynh · CAVAT</title>
      <div className="mx-auto max-w-4xl px-4 py-10">
        <section className="card brand-gradient grid items-center gap-6 p-6 md:grid-cols-[1fr_auto] md:p-8">
          <div>
            <h1 className="text-3xl font-extrabold md:text-4xl">Theo dõi việc học của con</h1>
            <p className="mt-2 text-lg text-slate-700">
              Xem con học có đều không, hiểu bài tới đâu và bố mẹ có thể giúp con ở nhà thế nào.
            </p>
            <form
              className="mt-5 flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                if (code.trim()) void navigate(`/parent/${code.trim().toUpperCase()}`);
              }}
            >
              <label className="flex flex-col gap-1.5">
                <span className="font-semibold">Mã học sinh của con</span>
                <input
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  maxLength={6}
                  placeholder="VD: 3F9A2C"
                  autoComplete="off"
                  className="w-48 rounded-2xl border-2 border-slate-300 bg-white px-4 py-2.5 font-mono text-2xl tracking-[0.2em] uppercase focus:border-brand-600"
                />
              </label>
              <button
                type="submit"
                disabled={!code.trim()}
                className="rounded-full bg-brand-700 px-6 py-3 text-lg font-semibold text-white hover:bg-brand-800 disabled:opacity-50"
              >
                Xem tình hình học
              </button>
            </form>
            <p className="mt-3 text-sm text-slate-600">
              Mã nằm ở trang học sinh của con, mục "Mã cho bố mẹ".
            </p>
          </div>
          <Mascot mood="encouraging" size={150} className="justify-self-center" />
        </section>
      </div>
    </AppShell>
  );
}

/** The child's progress for the parent: plain words, no score, no transcript (PART 27.1, 27.4). */
export function ParentChildPage() {
  const api = useApi();
  const { code = "" } = useParams();
  const child = useQuery({
    queryKey: ["child", code],
    queryFn: () => api.getChildOverview!(code),
    enabled: api.getChildOverview !== undefined,
    retry: false,
  });

  let body: ReactNode;
  if (!api.getChildOverview) {
    body = <Notice>Trang phụ huynh cần máy chủ thật. Hãy chạy bản demo bằng lệnh make demo.</Notice>;
  } else if (child.isPending) {
    body = <Notice>Đang tải tình hình học của con…</Notice>;
  } else if (child.isError) {
    const missing = child.error instanceof ApiError && child.error.code === "NOT_FOUND";
    body = (
      <Notice>
        {missing ? `Không tìm thấy học sinh có mã ${code}.` : "Chưa tải được, bố mẹ thử lại sau nhé."}{" "}
        <Link to="/parent" className="text-brand-800 underline">
          Nhập lại mã
        </Link>
      </Notice>
    );
  } else {
    body = <ChildView view={child.data} />;
  }
  return (
    <AppShell>
      <title>Tình hình học của con · CAVAT</title>
      <div className="mx-auto max-w-7xl px-4 py-8">{body}</div>
    </AppShell>
  );
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="card p-6 text-lg">
      {children}
    </p>
  );
}

function ChildView({ view }: { view: ParentChildView }) {
  const name = view.student_display_name || "con";
  return (
    <div className="flex flex-col gap-6">
      <header className="card brand-gradient flex flex-wrap items-center justify-between gap-4 p-6">
        <div>
          <h1 className="text-3xl font-extrabold">Tình hình học của {name}</h1>
          <p className="mt-1 text-lg text-slate-700">
            Chương {view.chapter.title}
            {view.last_session_at ? ` · buổi gần nhất ${formatViDateTime(view.last_session_at)}` : ""}
          </p>
        </div>
        <Mascot mood={view.passed > 0 ? "celebrating" : "happy"} size={96} />
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          icon={<BookIcon className="size-5 text-sky-700" />}
          label="Số buổi học"
          value={`${view.sessions.total}`}
        >
          {view.sessions.completed} buổi xong, {view.sessions.unfinished} buổi dở dang
        </Kpi>
        <Kpi
          icon={<ClockIcon className="size-5 text-brand-700" />}
          label="Thời gian học"
          value={minutesText(view.sessions.minutes, view.sessions.total)}
        >
          ước tính từ các lượt học, bỏ qua lúc nghỉ lâu
        </Kpi>
        <Kpi
          icon={<CheckIcon className="size-5 text-emerald-600" />}
          label="Bài đã vững"
          value={`${view.passed}/${view.total}`}
        >
          đủ bằng chứng mới tính là qua bài
        </Kpi>
        <Kpi
          icon={<FlameIcon className="size-5 text-orange-500" />}
          label="Chuỗi ngày học"
          value={`${view.streak} ngày`}
        >
          {view.this_week.study_days} ngày trong tuần này
        </Kpi>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <section aria-labelledby="understanding-title" className="card p-6">
          <h2 id="understanding-title" className="text-xl font-bold">
            Con hiểu bài thế nào
          </h2>
          <p className="mb-4 text-slate-600">
            Theo thứ tự học của chương. Cô nhận xét dựa trên cách con làm bài, không chỉ dựa vào đúng hay sai.
          </p>
          <ol className="flex flex-col gap-2">
            {view.nodes.map((node) => {
              const state = topicState(node);
              return (
                <li
                  key={node.node_id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-slate-50 px-4 py-3"
                >
                  <span>
                    <span className="block font-semibold">{node.name}</span>
                    <span className="text-sm text-slate-600">{state.meaning}</span>
                  </span>
                  <span
                    className={`shrink-0 rounded-full px-3 py-1 text-sm font-semibold ring-1 ${state.tone}`}
                  >
                    {state.label}
                  </span>
                </li>
              );
            })}
          </ol>
          <details className="mt-4 text-sm text-slate-700">
            <summary className="cursor-pointer font-semibold">Các mức nhận xét nghĩa là gì?</summary>
            <ul className="mt-2 flex flex-col gap-1.5">
              {QUALITY_ORDER.map((q) => (
                <li key={q} className="flex items-start gap-2">
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${QUALITY_TONE[q]}`}
                  >
                    {QUALITY_LABEL[q]}
                  </span>
                  {QUALITY_MEANING[q]}
                </li>
              ))}
            </ul>
          </details>
        </section>

        <div className="flex flex-col gap-6">
          <section
            aria-labelledby="good-title"
            className="rounded-3xl border border-emerald-200 bg-emerald-50 p-6"
          >
            <h2 id="good-title" className="text-lg font-bold text-emerald-900">
              Con đang làm tốt
            </h2>
            {view.going_well.length === 0 ? (
              <p className="mt-2 text-emerald-950/80">
                Chưa có bài nào con tự làm vững. Con đang trên đường!
              </p>
            ) : (
              <ul className="mt-2 flex flex-col gap-2">
                {view.going_well.map((t) => (
                  <li key={t.node_id} className="flex items-center gap-2 font-semibold text-emerald-950">
                    <SparklesIcon className="size-5 text-emerald-600" />
                    {t.name}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section
            aria-labelledby="practise-title"
            className="rounded-3xl border border-amber-200 bg-amber-50 p-6"
          >
            <h2 id="practise-title" className="text-lg font-bold text-amber-900">
              Con cần luyện thêm
            </h2>
            {view.to_practise.length === 0 ? (
              <p className="mt-2 text-amber-950/80">Hiện chưa có bài nào cần ôn.</p>
            ) : (
              <ul className="mt-2 flex flex-col gap-3">
                {view.to_practise.map((t) => (
                  <li key={t.node_id}>
                    <p className="font-semibold text-amber-950">{t.name}</p>
                    <p className="text-sm text-amber-950/80">{t.reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-labelledby="tips-title" className="card p-6">
            <h2 id="tips-title" className="flex items-center gap-2 text-lg font-bold">
              <HeartIcon className="size-5 text-rose-500" /> Gợi ý cho bố mẹ
            </h2>
            <ul className="mt-3 flex flex-col gap-3">
              {view.home_tips.map((tip) => (
                <li key={tip.node_id} className="rounded-2xl bg-sky-soft p-3">
                  <p className="text-sm font-semibold text-sky-900">{tip.name}</p>
                  <p className="text-slate-800">{tip.tip}</p>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>

      <section aria-labelledby="trend-title" className="card p-6">
        <h2 id="trend-title" className="flex items-center gap-2 text-xl font-bold">
          <TargetIcon className="size-5 text-brand-700" /> Tiến bộ 4 tuần: số bài con đã qua
        </h2>
        <p className="mb-4 text-slate-600">
          Mỗi bậc thang là một bài con học vững. Ô màu cam là ngày con có học.
        </p>
        <ProgressTrend trend={view.trend} total={view.total} />
      </section>

      <section aria-labelledby="sessions-title" className="card p-6">
        <h2 id="sessions-title" className="text-xl font-bold">
          Các buổi học
        </h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left">
            <thead className="text-sm text-slate-600">
              <tr>
                <th className="py-2 pr-4 font-medium">Bắt đầu</th>
                <th className="py-2 pr-4 font-medium">Thời gian</th>
                <th className="py-2 pr-4 font-medium">Trạng thái</th>
                <th className="py-2 font-medium">Bài con qua trong buổi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {view.session_list.map((s) => (
                <tr key={s.session_id}>
                  <td className="py-2 pr-4 whitespace-nowrap">{formatViDateTime(s.started_at)}</td>
                  <td className="py-2 pr-4 whitespace-nowrap">{minutesText(s.minutes, 1)}</td>
                  <td className="py-2 pr-4">{LIFECYCLE_LABEL[s.lifecycle_state]}</td>
                  <td className="py-2">{s.passed_names.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Kpi({
  icon,
  label,
  value,
  children,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  children: ReactNode;
}) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between text-sm text-slate-600">
        {label}
        {icon}
      </div>
      <div className="mt-2 text-3xl font-bold">{value}</div>
      <div className="mt-1 text-sm text-slate-600">{children}</div>
    </div>
  );
}
