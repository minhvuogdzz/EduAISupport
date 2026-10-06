import { Link } from "react-router";

import { useApi } from "../api/apiContext";
import { MockBanner } from "../components/MockBanner";

export function HomePage() {
  // The real API teaches the chapter on its knowledge graph; the in-browser mock still runs lesson 1.
  const live = useApi().engine === "live";
  return (
    <div className="min-h-dvh bg-amber-50">
      <title>CAVAT — Gia sư AI lớp 5</title>
      <MockBanner />
      <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
        <header className="flex flex-col gap-2">
          <h1 className="text-4xl font-bold">CAVAT — Gia sư AI lớp 5</h1>
          <p className="text-xl text-slate-700">
            {live ? "Toán lớp 5 · Chương Số thập phân" : "Toán lớp 5 · Bài 1: So sánh hai số thập phân"}
          </p>
        </header>
        <nav aria-label="Chọn vai trò" className="grid gap-4 sm:grid-cols-2">
          <Link
            to="/student"
            className="flex flex-col gap-2 rounded-3xl bg-teal-700 p-6 text-white shadow-sm hover:bg-teal-800"
          >
            <span className="text-3xl font-bold">Học sinh</span>
            <span className="text-xl">Vào học cùng cô</span>
          </Link>
          <Link
            to="/teacher"
            className="flex flex-col gap-2 rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-200 hover:ring-teal-600"
          >
            <span className="text-3xl font-bold">Giáo viên</span>
            <span className="text-xl text-slate-700">
              {live ? "Xem cô dạy, chấm điểm và quyết định thế nào" : "Xem transcript các buổi học"}
            </span>
          </Link>
        </nav>
      </main>
    </div>
  );
}
