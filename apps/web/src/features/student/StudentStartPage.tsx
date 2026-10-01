import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { useApi } from "../../api/apiContext";
import { MockBanner } from "../../components/MockBanner";
import { readLastSessionId, rememberSession } from "./lastSession";

/**
 * Temporary entry for students: a given name starts a demo session (POST /v1/sessions of T08).
 * Replaced by login with class code + PIN and "Đã đến giờ học" once identity and scheduling exist.
 */
export function StudentStartPage() {
  const api = useApi();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [lastSessionId] = useState(readLastSessionId);

  const last = useQuery({
    queryKey: ["session-state", lastSessionId],
    queryFn: () => api.getState(lastSessionId ?? ""),
    enabled: lastSessionId !== null,
    retry: false,
  });
  const resumable = last.data && last.data.lifecycle_state !== "COMPLETED" ? last.data : null;

  const start = useMutation({
    mutationFn: (studentName: string) => api.createDemoSession({ student_display_name: studentName }),
    onSuccess: ({ session_id }) => {
      rememberSession(session_id);
      void navigate(`/student/sessions/${session_id}`);
    },
  });

  return (
    <div className="min-h-dvh bg-amber-50">
      <title>Vào học · CAVAT</title>
      <MockBanner />
      <main className="mx-auto flex max-w-xl flex-col gap-8 px-4 py-10">
        <h1 className="text-4xl font-bold">Chào con!</h1>

        {resumable && (
          <section className="flex flex-col gap-3 rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
            <p className="text-xl">
              Buổi học của <strong>{resumable.student_display_name}</strong> còn dang dở (đã xong{" "}
              {resumable.progress.items_done}/{resumable.progress.items_total} câu).
            </p>
            <Link
              to={`/student/sessions/${resumable.session_id}`}
              className="self-start rounded-2xl bg-teal-700 px-6 py-3 text-xl font-semibold text-white hover:bg-teal-800"
            >
              Học tiếp
            </Link>
          </section>
        )}

        <form
          className="flex flex-col gap-3 rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-200"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) start.mutate(name.trim());
          }}
        >
          <label htmlFor="student-name" className="text-2xl font-semibold">
            Con tên là gì?
          </label>
          <p id="student-name-help" className="text-lg text-slate-600">
            Chỉ cần tên gọi, ví dụ: Minh.
          </p>
          <input
            id="student-name"
            aria-describedby="student-name-help"
            value={name}
            maxLength={30}
            autoComplete="given-name"
            onChange={(event) => setName(event.target.value)}
            className="rounded-2xl border-2 border-slate-300 px-4 py-3 text-2xl focus:border-teal-600"
          />
          <button
            type="submit"
            disabled={!name.trim() || start.isPending}
            className="mt-2 rounded-2xl bg-teal-700 px-6 py-4 text-2xl font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
          >
            Bắt đầu học
          </button>
          {start.isError && (
            <p role="alert" className="text-lg text-red-700">
              Chưa tạo được buổi học. Con thử lại nhé.
            </p>
          )}
        </form>

        <Link to="/" className="text-lg text-teal-800 underline">
          Về trang chính
        </Link>
      </main>
    </div>
  );
}
