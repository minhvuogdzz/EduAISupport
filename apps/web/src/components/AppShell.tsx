import type { ReactNode } from "react";
import { Link, NavLink } from "react-router";

import { useAuth } from "../features/auth/authContext";
import { Mascot } from "./Mascot";
import { MockBanner } from "./MockBanner";

const NAV = [
  { to: "/", label: "Trang chủ", end: true, kind: null },
  { to: "/student", label: "Học sinh", end: false, kind: "STUDENT" },
  { to: "/parent", label: "Phụ huynh", end: false, kind: "PARENT" },
  { to: "/teacher", label: "Giáo viên", end: false, kind: "TEACHER" },
] as const;

/**
 * The frame of every page but the lesson itself: brand, the roles, a footer. A logged-in account (ACC-1)
 * sees only its own area and a "Đăng xuất" button; the mock API and the demo mode show every role.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const items = NAV.filter((item) => !user || item.kind === null || item.kind === user.kind);
  return (
    <div className="flex min-h-dvh flex-col">
      <MockBanner />
      <header className="sticky top-0 z-30 border-b border-gold/25 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4">
          <Link to="/" className="flex shrink-0 items-center gap-2 rounded-2xl" aria-label="CAVAT, trang chủ">
            <Mascot size={42} />
            <span className="flex flex-col leading-tight">
              <span className="text-lg font-extrabold tracking-tight text-brand-900">CAVAT</span>
              <span className="hidden text-xs text-slate-600 sm:block">Gia sư AI · Toán lớp 5</span>
            </span>
          </Link>
          <nav aria-label="Vai trò" className="-mr-2 flex items-center gap-1 overflow-x-auto">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `shrink-0 rounded-full px-3.5 py-2 text-sm font-semibold transition ${
                    isActive
                      ? "bg-brand-700 text-white"
                      : "text-slate-700 hover:bg-brand-50 hover:text-brand-900"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            {user && (
              <button
                type="button"
                onClick={logout}
                className="shrink-0 rounded-full px-3.5 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                title={`Đang đăng nhập: ${user.display_name}`}
              >
                Đăng xuất
              </button>
            )}
          </nav>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-gold/25 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-6 text-sm text-slate-600">
          <p>
            <span className="font-semibold text-brand-900">CAVAT</span> · Gia sư AI dạy Toán lớp 5 · Chương Số
            thập phân
          </p>
          <p>Cô không làm bài thay con. Cô giúp con hiểu cách làm.</p>
        </div>
      </footer>
    </div>
  );
}
