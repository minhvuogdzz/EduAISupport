import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { useApi } from "../../api/apiContext";
import type { ClassOverview } from "../../api/contract";
import { AppShell } from "../../components/AppShell";
import { AlertIcon, BookIcon, CheckIcon, ChartIcon, UsersIcon } from "../../components/icons";
import { attentionText } from "../../components/labels";
import { formatViDecimal } from "../../lib/viNumber";
import { Heatmap } from "./analytics/Heatmap";
import { columns, urgency } from "./analytics/helpers";
import { MisconceptionChart } from "./analytics/MisconceptionChart";
import { zoneOf } from "./analytics/zones";
import { TeacherHeader } from "./TeacherHeader";

/**
 * The teacher's class dashboard (blueprint PART 27.1 "Class", khung Toán §45, §46, §28): who is where on
 * each KC of the chapter, what the class gets wrong, and who needs the teacher now.
 */
export function ClassPage() {
  const api = useApi();
  const overview = useQuery({
    queryKey: ["class-overview"],
    queryFn: () => api.getClassOverview!(),
    enabled: api.getClassOverview !== undefined,
    refetchInterval: 10_000,
    retry: false,
  });

  let body: ReactNode;
  if (!api.getClassOverview) {
    body = (
      <Notice>
        Bảng theo dõi lớp cần máy chủ thật: chạy bản demo bằng lệnh make demo.{" "}
        <Link to="/teacher/sessions" className="text-brand-800 underline">
          Xem từng buổi học
        </Link>
      </Notice>
    );
  } else if (overview.isPending) {
    body = <Notice>Đang tải bảng theo dõi lớp…</Notice>;
  } else if (overview.isError) {
    body = <Notice>Chưa tải được bảng theo dõi lớp, cô thử lại sau nhé.</Notice>;
  } else if (overview.data.students.length === 0) {
    body = <Notice>Chưa có học sinh nào học chương {overview.data.chapter.title}.</Notice>;
  } else {
    body = <ClassDashboard overview={overview.data} />;
  }
  return (
    <AppShell>
      <title>Lớp học · CAVAT</title>
      <TeacherHeader title={overview.data ? `Lớp học · ${overview.data.chapter.title}` : "Lớp học"} />
      <div className="mx-auto max-w-7xl px-4 pb-10">{body}</div>
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

function ClassDashboard({ overview }: { overview: ClassOverview }) {
  const k = overview.kpis;
  const nodeName = (id: string) => overview.nodes.find((n) => n.node_id === id)?.name ?? id;
  const misName = (id: string) => overview.misconceptions.find((m) => m.id === id)?.name ?? id;
  const flagged = overview.students.filter((s) => s.attention.length > 0);
  const recurring = [...overview.misconceptions].sort((a, b) => b.recent - a.recent || b.count - a.count)[0];
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Kpi icon={<UsersIcon className="size-5 text-sky-700" />} label="Học sinh" value={`${k.students}`}>
          {k.active_this_week} em học trong tuần này
        </Kpi>
        <Kpi icon={<BookIcon className="size-5 text-brand-700" />} label="Buổi học" value={`${k.sessions}`}>
          {k.minutes} phút học
        </Kpi>
        <Kpi
          icon={<CheckIcon className="size-5 text-emerald-600" />}
          label="Lượt qua bài"
          value={`${k.passed}/${k.cells}`}
        >
          {formatViDecimal(k.cells ? Math.round((1000 * k.passed) / k.cells) / 10 : 0)}% số ô học sinh × bài
        </Kpi>
        <Kpi
          icon={<ChartIcon className="size-5 text-brand-700" />}
          label="Điểm hiểu bài trung bình"
          value={k.mean_mastery === null ? "–" : formatViDecimal(k.mean_mastery)}
          tone={k.mean_mastery === null ? undefined : zoneOf(k.mean_mastery).cell}
        >
          trung bình điểm tổng của các em (DI-21)
        </Kpi>
        <Kpi icon={<AlertIcon className="size-5 text-rose-600" />} label="Cần chú ý" value={`${k.attention}`}>
          học sinh
        </Kpi>
      </div>

      <section aria-labelledby="heatmap-title" className="card flex flex-col gap-3 p-5">
        <div>
          <h2 id="heatmap-title" className="text-xl font-bold">
            Học sinh × bài học
          </h2>
          <p className="text-slate-600">
            Mỗi ô là điểm hiểu bài M (0–100) của một em ở một bài (khung Toán §46), tô theo 5 vùng màu của
            §25. Hàng cuối là cả lớp (§45). Bấm vào một ô để xem chi tiết bài đó của em.
          </p>
        </div>
        <Heatmap overview={overview} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="mis-title" className="card flex flex-col gap-4 p-5">
          <h2 id="mis-title" className="text-xl font-bold">
            Lỗi sai phổ biến của lớp
          </h2>
          {recurring && (
            <div className="rounded-2xl bg-rose-50 p-4 text-sm ring-1 ring-rose-200">
              <p>
                <span className="font-semibold">Lỗi tái diễn nhiều nhất:</span> {recurring.name}
              </p>
              <p>
                <span className="font-semibold">Xuất hiện:</span> {recurring.recent} lần / 14 ngày ·{" "}
                {recurring.active_students} em còn đang mắc
              </p>
              <p>
                <span className="font-semibold">Mức độ:</span> {urgency(recurring)}
              </p>
            </div>
          )}
          <MisconceptionChart
            empty="Chưa phát hiện lỗi sai nào trong lớp."
            items={overview.misconceptions.map((m) => ({
              ...m,
              note: `${m.students} em từng mắc, ${m.active_students} em còn mắc${
                m.node_id ? ` · bài ${nodeName(m.node_id)}` : ""
              }`,
            }))}
          />
          <p className="text-xs text-slate-500">
            Tỉ lệ là phần trăm trên tổng số lần phát hiện lỗi của cả lớp (khung Toán §28). Mức độ: "Cần can
            thiệp" khi lỗi nghiêm trọng hoặc gặp từ 3 lần trong 14 ngày mà vẫn còn em mắc (DI-28).
          </p>
        </section>

        <section aria-labelledby="attention-title" className="card flex flex-col gap-3 p-5">
          <h2 id="attention-title" className="text-xl font-bold">
            Học sinh cần chú ý
          </h2>
          {flagged.length === 0 ? (
            <p className="text-slate-600">Hiện chưa có em nào cần cô can thiệp.</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {flagged.map((s) => (
                <li key={s.student_id} className="rounded-2xl bg-rose-50/60 p-3 ring-1 ring-rose-200">
                  <Link
                    to={`/teacher/students/${encodeURIComponent(s.student_id)}`}
                    className="font-semibold text-brand-900 hover:underline"
                  >
                    {s.display_name}
                  </Link>
                  <ul className="mt-1 list-disc pl-5 text-sm text-slate-800">
                    {s.attention.map((reason, i) => (
                      <li key={i}>{attentionText(reason, nodeName, misName)}</li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-slate-500">
            Lý do được xét: lỗi nghiêm trọng hoặc lặp lại từ 2 lần mà còn mắc; gia sư đã dừng một bài; bài ở
            vùng đỏ khi đã đủ dữ liệu; buổi học dở dang mà 7 ngày chưa quay lại (DI-20).
          </p>
        </section>
      </div>

      <section aria-labelledby="by-node-title" className="card flex flex-col gap-3 p-5">
        <h2 id="by-node-title" className="text-xl font-bold">
          Cả lớp theo từng bài
        </h2>
        <p className="text-slate-600">
          Trung bình điểm M của các em đã có điểm ở bài đó (khung Toán §45): bài nào cả lớp đang gặp khó.
        </p>
        <ul className="flex flex-col gap-2">
          {columns(overview.nodes).map((n) => {
            const b = overview.by_node.find((x) => x.node_id === n.node_id);
            const mean = b?.mean_mastery ?? null;
            return (
              <li key={n.node_id} className="grid items-center gap-3 sm:grid-cols-[16rem_1fr_15rem]">
                <span className="font-medium">{n.name}</span>
                <span className="h-4 rounded-full bg-slate-100">
                  {mean !== null && (
                    <span
                      className={`block h-4 rounded-full ${zoneOf(mean).cell}`}
                      style={{ width: `${mean}%` }}
                    />
                  )}
                </span>
                <span className="text-sm text-slate-700 tabular-nums">
                  {mean === null
                    ? "chưa em nào có điểm"
                    : `${formatViDecimal(mean)} · ${b?.students} em có điểm · ${b?.passed} em qua bài`}
                </span>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}

function Kpi({
  icon,
  label,
  value,
  tone,
  children,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone?: string;
  children: ReactNode;
}) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between text-sm text-slate-600">
        {label}
        {icon}
      </div>
      <div className="mt-2 text-3xl font-bold tabular-nums">
        {tone ? <span className={`rounded-xl px-2 ${tone}`}>{value}</span> : value}
      </div>
      <div className="mt-1 text-sm text-slate-600">{children}</div>
    </div>
  );
}
