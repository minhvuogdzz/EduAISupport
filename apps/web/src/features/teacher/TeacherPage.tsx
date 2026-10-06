import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";

import { useApi } from "../../api/apiContext";
import { AppShell } from "../../components/AppShell";
import { BrainPanel } from "./BrainPanel";
import { SessionList } from "./SessionList";
import { TeacherHeader } from "./TeacherHeader";
import { TranscriptView } from "./TranscriptView";

/** Teacher: list of sessions; for the selected one, the tutor's reasoning (chapter sessions) and the transcript. */
export function TeacherPage() {
  const api = useApi();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.listSessions(),
    refetchInterval: 5000,
  });
  const selectedId = sessionId ?? sessions.data?.[0]?.session_id ?? null;
  const selectedMode = sessions.data?.find((s) => s.session_id === selectedId)?.mode;

  async function resetDemoData() {
    if (
      !api.resetDemoData ||
      !window.confirm("Xóa mọi buổi học demo trong trình duyệt này và tạo lại dữ liệu mẫu?")
    ) {
      return;
    }
    await api.resetDemoData();
    await queryClient.invalidateQueries();
    await navigate("/teacher/sessions");
  }

  return (
    <AppShell>
      <title>Giáo viên · CAVAT</title>
      <TeacherHeader title="Buổi học">
        {api.resetDemoData && (
          <button
            type="button"
            onClick={() => void resetDemoData()}
            className="rounded-full px-4 py-2 text-sm text-slate-700 ring-1 ring-slate-300 hover:bg-slate-100"
          >
            Tạo lại dữ liệu demo
          </button>
        )}
      </TeacherHeader>
      <div className="mx-auto grid max-w-7xl gap-6 px-4 pb-6 lg:grid-cols-[20rem_1fr]">
        <aside>
          <h2 className="mb-3 text-lg font-semibold">Buổi học</h2>
          {sessions.isPending ? (
            <p className="text-slate-600">Đang tải…</p>
          ) : sessions.isError ? (
            <p role="alert">Không tải được danh sách buổi học.</p>
          ) : (
            <SessionList sessions={sessions.data} selectedId={selectedId} />
          )}
        </aside>
        <main>
          {selectedId ? (
            <SessionPanel key={selectedId} sessionId={selectedId} chapter={selectedMode === "CHAPTER"} />
          ) : (
            !sessions.isPending && <p className="text-slate-600">Chọn một buổi học để xem transcript.</p>
          )}
        </main>
      </div>
    </AppShell>
  );
}

/** A chapter session opens on the tutor's reasoning; the transcript is the second tab. */
function SessionPanel({ sessionId, chapter }: { sessionId: string; chapter: boolean }) {
  const api = useApi();
  const [tab, setTab] = useState<"brain" | "transcript">("brain");
  if (!chapter || !api.getReport) return <TranscriptPanel sessionId={sessionId} />;
  const tabs = [
    ["brain", "Bộ não gia sư"],
    ["transcript", "Hội thoại"],
  ] as const;
  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" aria-label="Xem buổi học" className="flex gap-2">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`tab-${key}`}
            aria-selected={tab === key}
            aria-controls={`panel-${key}`}
            onClick={() => setTab(key)}
            className={`rounded-xl px-4 py-2 font-semibold ${
              tab === key
                ? "bg-brand-700 text-white"
                : "bg-white text-slate-800 ring-1 ring-slate-300 hover:bg-slate-100"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "brain" ? <ReportPanel sessionId={sessionId} /> : <TranscriptPanel sessionId={sessionId} />}
      </div>
    </div>
  );
}

function ReportPanel({ sessionId }: { sessionId: string }) {
  const api = useApi();
  const report = useQuery({
    queryKey: ["report", sessionId],
    queryFn: () => api.getReport!(sessionId),
    // Follow a session in progress live, like the transcript.
    refetchInterval: (query) => (query.state.data?.session.lifecycle_state === "ACTIVE" ? 3000 : false),
  });
  if (report.isPending) return <p className="text-slate-600">Đang tải…</p>;
  if (report.isError) return <p role="alert">Không tải được báo cáo của buổi học này.</p>;
  return <BrainPanel report={report.data} />;
}

function TranscriptPanel({ sessionId }: { sessionId: string }) {
  const api = useApi();
  const transcript = useQuery({
    queryKey: ["transcript", sessionId],
    queryFn: () => api.getTranscript(sessionId),
    // A session in progress keeps growing: follow it live (PART 24.5).
    refetchInterval: (query) => (query.state.data?.session.lifecycle_state === "ACTIVE" ? 3000 : false),
  });
  if (transcript.isPending) return <p className="text-slate-600">Đang tải transcript…</p>;
  if (transcript.isError) return <p role="alert">Không tải được transcript của buổi học này.</p>;
  return <TranscriptView transcript={transcript.data} />;
}
