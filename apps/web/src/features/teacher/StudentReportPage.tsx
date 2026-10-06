import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { useApi } from "../../api/apiContext";
import { ApiError } from "../../api/client";
import type { Dimension, KcGroup, TeacherNodeDetail, TeacherStudentView } from "../../api/contract";
import { AppShell } from "../../components/AppShell";
import {
  attentionText,
  DIMENSION_LABEL,
  KC_GROUP_LABEL,
  KC_GROUP_MARK,
  LIFECYCLE_LABEL,
  minutesText,
} from "../../components/labels";
import { formatViDateTime, formatViDecimal } from "../../lib/viNumber";
import { KnowledgeMap } from "../teaching/KnowledgeMap";
import { ActivityChart } from "./analytics/ActivityChart";
import { KcDetail } from "./analytics/KcDetail";
import { MasteryGauge } from "./analytics/MasteryGauge";
import { MasteryTimeline } from "./analytics/MasteryTimeline";
import { RadarChart } from "./analytics/RadarChart";
import { zoneOf } from "./analytics/zones";
import { TeacherHeader } from "./TeacherHeader";

const GROUP_ORDER: KcGroup[] = ["PASSED", "UNSTABLE", "WEAK", "INSUFFICIENT", "NOT_STARTED"];

/** One student on the chapter for the teacher (blueprint PART 27.1; khung Toán §23, §24, §27, §43, §56, §57). */
export function StudentReportPage() {
  const api = useApi();
  const { studentId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const report = useQuery({
    queryKey: ["student-report", studentId],
    queryFn: () => api.getStudentReport!(studentId),
    enabled: api.getStudentReport !== undefined,
    refetchInterval: 10_000,
    retry: false,
  });

  let body: ReactNode;
  if (!api.getStudentReport) {
    body = <Notice>Báo cáo học sinh cần máy chủ thật: chạy bản demo bằng lệnh make demo.</Notice>;
  } else if (report.isPending) {
    body = <Notice>Đang tải báo cáo…</Notice>;
  } else if (report.isError) {
    const missing = report.error instanceof ApiError && report.error.code === "NOT_FOUND";
    body = (
      <Notice>
        {missing ? "Em này chưa học buổi nào của chương." : "Chưa tải được báo cáo, cô thử lại sau nhé."}{" "}
        <Link to="/teacher" className="text-brand-800 underline">
          Về bảng theo dõi lớp
        </Link>
      </Notice>
    );
  } else {
    body = (
      <StudentReport
        view={report.data}
        selected={params.get("node")}
        onSelect={(nodeId) => setParams({ node: nodeId }, { replace: true, preventScrollReset: true })}
      />
    );
  }
  return (
    <AppShell>
      <title>{report.data ? `${report.data.display_name} · Giáo viên · CAVAT` : "Học sinh · CAVAT"}</title>
      <TeacherHeader title={report.data ? `Học sinh ${report.data.display_name}` : "Học sinh"} />
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

/** The KC shown first: the one asked for, else the one being learned, else the last one with a score. */
function pick(nodes: TeacherNodeDetail[], selected: string | null): TeacherNodeDetail {
  return (
    nodes.find((n) => n.node_id === selected) ??
    nodes.find((n) => n.status === "CURRENT") ??
    [...nodes].reverse().find((n) => n.mastery !== null) ??
    nodes[0]
  );
}

function dimensionList(dims: Dimension[], view: TeacherStudentView): string {
  return dims
    .map((d) => `${DIMENSION_LABEL[d]} (${formatViDecimal(view.dimensions[d].value ?? 0)})`)
    .join(", ");
}

function StudentReport({
  view,
  selected,
  onSelect,
}: {
  view: TeacherStudentView;
  selected: string | null;
  onSelect: (nodeId: string) => void;
}) {
  const node = pick(view.nodes, selected);
  const nodeName = (id: string) => view.nodes.find((n) => n.node_id === id)?.name ?? id;
  const misName = (id: string) =>
    view.nodes.flatMap((n) => n.misconceptions).find((m) => m.id === id)?.name ?? id;
  const risks = view.nodes.filter(
    (n) => n.group === "WEAK" || n.misconceptions.some((m) => m.status !== "RESOLVED"),
  );
  const o = view.overall;
  const values = Object.fromEntries(Object.entries(view.dimensions).map(([d, v]) => [d, v.value])) as Record<
    Dimension,
    number | null
  >;
  return (
    <div className="flex flex-col gap-6">
      <section className="card brand-gradient flex flex-wrap items-start justify-between gap-4 p-5">
        <div>
          <p className="text-lg">
            Chương {view.chapter.title} · {view.sessions.total} buổi ({view.sessions.completed} xong,{" "}
            {view.sessions.unfinished} dở dang) · {minutesText(view.sessions.minutes, view.sessions.total)}
          </p>
          {view.last_active_at && (
            <p className="text-slate-700">Lần học gần nhất: {formatViDateTime(view.last_active_at)}</p>
          )}
        </div>
        {view.attention.length > 0 && (
          <div className="rounded-2xl bg-white/85 p-3 ring-1 ring-rose-200">
            <p className="font-semibold text-rose-900">Cần chú ý</p>
            <ul className="list-disc pl-5 text-sm">
              {view.attention.map((r, i) => (
                <li key={i}>{attentionText(r, nodeName, misName)}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section aria-labelledby="overall-title" className="card flex flex-col items-center gap-3 p-5">
          <h2 id="overall-title" className="self-start text-lg font-bold">
            Tổng quan
          </h2>
          <MasteryGauge
            mastery={o.mastery}
            confidence={o.confidence}
            level={o.level}
            caption="Mức độ hiểu tổng thể"
          />
          <dl className="grid w-full grid-cols-2 gap-2 text-sm">
            <div className="rounded-2xl bg-slate-50 px-3 py-2">
              <dt className="text-slate-600">Phủ kiến thức</dt>
              <dd className="font-bold tabular-nums">
                {formatViDecimal(o.coverage)}%{" "}
                <span className="font-normal text-slate-600">số bài có điểm</span>
              </dd>
            </div>
            <div className="rounded-2xl bg-slate-50 px-3 py-2">
              <dt className="text-slate-600">Đã qua bài</dt>
              <dd className="font-bold tabular-nums">
                {o.passed}/{o.total}
              </dd>
            </div>
            <div className="col-span-2 rounded-2xl bg-slate-50 px-3 py-2">
              <dt className="text-slate-600">Tốc độ học (§39)</dt>
              <dd className="font-semibold">
                {view.velocity
                  ? `${view.velocity.change >= 0 ? "↑ +" : "↓ "}${formatViDecimal(view.velocity.change)} điểm so với trước tuần này`
                  : "Chưa đủ dữ liệu: cần điểm của tuần trước để so"}
              </dd>
            </div>
          </dl>
          <p className="text-xs text-slate-500">
            Điểm tổng là trung bình M của các bài đã có điểm; phủ kiến thức là phần bài đã có điểm (DI-21).
          </p>
        </section>

        <section aria-labelledby="radar-title" className="card flex flex-col gap-2 p-5">
          <h2 id="radar-title" className="text-lg font-bold">
            Các chiều hiểu bài
          </h2>
          <RadarChart values={values} />
          <div className="text-sm">
            <span className="text-slate-600">{DIMENSION_LABEL.D} (D): </span>
            <span className="font-semibold">
              {values.D === null ? "chưa đủ dữ liệu" : formatViDecimal(values.D)}
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Sáu trục theo khung Toán §24; trục Kiến thức đọc từ chiều C (làm đúng), D nằm ngoài radar. Mỗi
            chiều là trung bình các bài có đủ bằng chứng, theo lượng bằng chứng (DI-22). Vòng đứt nét là các
            mốc 40, 60, 75, 90 của §25.
          </p>
        </section>

        <section aria-labelledby="summary-title" className="card flex flex-col gap-3 p-5">
          <h2 id="summary-title" className="text-lg font-bold">
            Nhận định
          </h2>
          <Line label="Điểm mạnh">
            {view.strengths.length ? dimensionList(view.strengths, view) : "Chưa có chiều nào từ 75 trở lên"}
          </Line>
          <Line label="Điểm yếu">
            {view.weaknesses.length ? dimensionList(view.weaknesses, view) : "Không có chiều nào dưới 60"}
          </Line>
          <Line label="Rủi ro">
            {risks.length ? risks.map((n) => n.name).join(", ") : "Chưa thấy bài nào đáng lo"}
          </Line>
          <ul className="mt-1 flex flex-col gap-2">
            {GROUP_ORDER.map((g) => {
              const members = view.nodes.filter((n) => n.group === g);
              if (members.length === 0) return null;
              return (
                <li key={g} className="text-sm">
                  <span className="font-semibold">
                    {KC_GROUP_MARK[g]} {KC_GROUP_LABEL[g]}:
                  </span>{" "}
                  {members.map((n, i) => (
                    <span key={n.node_id}>
                      {i > 0 && ", "}
                      <button
                        type="button"
                        onClick={() => onSelect(n.node_id)}
                        className="text-brand-800 underline-offset-2 hover:underline"
                      >
                        {n.name}
                      </button>
                    </span>
                  ))}
                </li>
              );
            })}
          </ul>
          <p className="text-xs text-slate-500">
            ✓ đã qua bài theo điều kiện DI-15 (chưa có kiểm tra duy trì nên chưa gọi là làm chủ, §53); ✕ còn
            yếu khi M dưới 60 và đã đủ dữ liệu; ⚠ còn lại (DI-23, DI-27).
          </p>
        </section>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,27rem)_minmax(0,1fr)]">
        <section aria-labelledby="graph-title" className="card p-5 xl:sticky xl:top-20">
          <h2 id="graph-title" className="text-lg font-bold">
            Cây tri thức
          </h2>
          <p className="mb-3 text-sm text-slate-600">
            Vạch màu bên phải mỗi bài là vùng điểm M (§26). Bấm một bài để xem chi tiết.
          </p>
          <KnowledgeMap
            nodes={view.nodes.map((n) => ({ ...n, level: n.mastery === null ? null : n.level }))}
            relations={view.relations}
            title={`Cây tri thức chương ${view.chapter.title} của ${view.display_name}`}
            showMastery
            zoneFill={(n) => (n.mastery === null || n.mastery === undefined ? null : zoneOf(n.mastery).fill)}
            selectedId={node.node_id}
            onSelect={onSelect}
          />
        </section>
        <KcDetail node={node} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="timeline-title" className="card flex flex-col gap-2 p-5">
          <h2 id="timeline-title" className="text-lg font-bold">
            Tiến bộ theo ngày
          </h2>
          <p className="text-sm text-slate-600">
            Điểm tổng cuối mỗi ngày có bằng chứng mới (khung Toán §27, DI-26), trên nền 5 vùng màu.
          </p>
          <MasteryTimeline points={view.timeline} />
        </section>
        <section aria-labelledby="activity-title" className="card flex flex-col gap-2 p-5">
          <h2 id="activity-title" className="text-lg font-bold">
            Hoạt động học
          </h2>
          <p className="text-sm text-slate-600">
            Số câu mỗi ngày theo cách con hoàn thành, số gợi ý và ngày qua bài (khung Toán §56).
          </p>
          <ActivityChart days={view.activity} />
        </section>
      </div>

      <section aria-labelledby="sessions-title" className="card p-5">
        <h2 id="sessions-title" className="text-lg font-bold">
          Các buổi học
        </h2>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left">
            <thead className="text-sm text-slate-600">
              <tr>
                <th className="py-2 pr-4 font-medium">Bắt đầu</th>
                <th className="py-2 pr-4 font-medium">Thời gian</th>
                <th className="py-2 pr-4 font-medium">Trạng thái</th>
                <th className="py-2 pr-4 font-medium">Bài qua trong buổi</th>
                <th className="py-2 font-medium">
                  <span className="sr-only">Mở</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {view.session_list.map((s) => (
                <tr key={s.session_id}>
                  <td className="py-2 pr-4 whitespace-nowrap">{formatViDateTime(s.started_at)}</td>
                  <td className="py-2 pr-4 whitespace-nowrap">{minutesText(s.minutes, 1)}</td>
                  <td className="py-2 pr-4">{LIFECYCLE_LABEL[s.lifecycle_state]}</td>
                  <td className="py-2 pr-4">{s.passed_names.join(", ") || "—"}</td>
                  <td className="py-2">
                    <Link
                      to={`/teacher/sessions/${encodeURIComponent(s.session_id)}`}
                      className="whitespace-nowrap text-brand-800 underline"
                    >
                      Bộ não gia sư và hội thoại
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Line({ label, children }: { label: string; children: ReactNode }) {
  return (
    <p className="text-sm">
      <span className="font-semibold">{label}: </span>
      {children}
    </p>
  );
}
