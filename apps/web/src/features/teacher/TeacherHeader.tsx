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
];

/** The title of a teacher page and the two teacher views: the class, and the sessions one by one. */
export function TeacherHeader({ title, children }: { title: string; children?: ReactNode }) {
  const { pathname } = useLocation();
  return (
    <div className="mx-auto flex max-w-7xl flex-wrap items-end justify-between gap-3 px-4 pt-6 pb-4">
      <div>
        <nav aria-label="Giáo viên" className="mb-3 flex gap-2">
          {TABS.map((tab) => {
            const active = tab.match(pathname);
            return (
              <Link
                key={tab.to}
                to={tab.to}
                aria-current={active ? "page" : undefined}
                className={`rounded-full px-4 py-1.5 text-sm font-semibold ${
                  active
                    ? "bg-brand-700 text-white"
                    : "bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>
        <h1 className="text-3xl font-extrabold">{title}</h1>
      </div>
      {children}
    </div>
  );
}
