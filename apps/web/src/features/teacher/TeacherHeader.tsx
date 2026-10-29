import type { ReactNode } from "react";
import { Link, useLocation } from "react-router";

const TABS = [
  {
    to: "/teacher",
    label: "Lớp học",
    match: (path: string) => path === "/teacher" || path.startsWith("/teacher/students"),
  },
  {
    to: "/teacher/sessions",
    label: "Buổi học",
    match: (path: string) => path.startsWith("/teacher/sessions"),
  },
  {
    to: "/teacher/lessons",
    label: "Bài học",
    match: (path: string) => path.startsWith("/teacher/lessons"),
  },
  {
    to: "/teacher/documents",
    label: "Tài liệu",
    match: (path: string) => path.startsWith("/teacher/documents"),
  },
  {
    to: "/teacher/rag",
    label: "RAG",
    match: (path: string) => path.startsWith("/teacher/rag"),
  },
];

/** The title of a teacher page and the two teacher views: the class, and the sessions one by one. */
export function TeacherHeader({ title, children }: { title: string; children?: ReactNode }) {
  const { pathname } = useLocation();
  return (
    <div className="teacher-heading">
      <div className="max-w-full min-w-0">
        <nav aria-label="Giáo viên" className="teacher-tabs">
          {TABS.map((tab) => {
            const active = tab.match(pathname);
            return (
              <Link
                key={tab.to}
                to={tab.to}
                aria-current={active ? "page" : undefined}
                className="teacher-tab"
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>
        <p className="eyebrow mb-3 text-slate-500">GÓC GIÁO VIÊN</p>
        <h1 className="text-2xl font-extrabold">{title}</h1>
      </div>
      {children}
    </div>
  );
}
