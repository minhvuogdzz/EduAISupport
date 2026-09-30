import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";

import { useApi } from "../../api/apiContext";
import { MockBanner } from "../../components/MockBanner";
import { SessionList } from "./SessionList";
import { TranscriptView } from "./TranscriptView";

/** Teacher: list of sessions and the transcript of the selected one (T09). */
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

  async function resetDemoData() {
    if (
      !api.resetDemoData ||
      !window.confirm("Xóa mọi buổi học demo trong trình duyệt này và tạo lại dữ liệu mẫu?")
    ) {
      return;
    }
    await api.resetDemoData();
    await queryClient.invalidateQueries();
    await navigate("/teacher");
  }

  return (
    <div className="min-h-dvh bg-slate-50">
      <title>Transcript · CAVAT</title>
      <MockBanner />
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
          <Link to="/" className="rounded-lg bg-teal-700 px-2 py-1 font-bold text-white">
            CAVAT
          </Link>
          <h1 className="flex-1 text-xl font-semibold">Giáo viên · Transcript buổi học</h1>
          {api.resetDemoData && (
            <button
              type="button"
              onClick={() => void resetDemoData()}
              className="rounded-xl px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-300 hover:bg-slate-100"
            >
              Tạo lại dữ liệu demo
            </button>
          )}
        </div>
      </header>
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[20rem_1fr]">
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
            <TranscriptPanel sessionId={selectedId} />
          ) : (
            !sessions.isPending && <p className="text-slate-600">Chọn một buổi học để xem transcript.</p>
          )}
        </main>
      </div>
    </div>
  );
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
