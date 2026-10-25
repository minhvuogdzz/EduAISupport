import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate } from "react-router";

import type { AccountKind } from "../api/contract";
import { ChildForm, PinForm } from "../features/auth/AuthGate";
import { homeOf, ROLE_LABEL, ROLES, roleOfPath, useAuth } from "../features/auth/authContext";
import { Mascot } from "./Mascot";
import { MockBanner } from "./MockBanner";

/** Each role has its colour, so the screen says at a glance whose area it is (ACC-2). */
const ROLE_TONE: Record<AccountKind, string> = {
  STUDENT: "bg-brand-700 text-white",
  PARENT: "bg-amber-600 text-white",
  TEACHER: "bg-indigo-700 text-white",
};

/**
 * The frame of every page but the lesson itself: brand, the role switcher, a footer.
 *
 * The trial has one student, one parent and one teacher (ACC-1). Nobody logs out (ACC-2): the switcher
 * opens another role. With accounts, a role asks its PIN the first time it is opened on this device and is
 * kept after that; the server checks every request against the current role's login (CLAUDE.md rule 4).
 * Without accounts (mock API, demo mode) the switcher only opens that role's area.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const current = user?.kind ?? roleOfPath(pathname);
  return (
    <div className="flex min-h-dvh flex-col">
      <MockBanner />
      <header className="sticky top-0 z-30 border-b border-gold/25 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4">
          <Link
            to={user ? homeOf(user.kind) : "/"}
            className="flex shrink-0 items-center gap-2 rounded-2xl"
            aria-label="CAVAT, trang chủ"
          >
            <Mascot size={42} />
            <span className="hidden flex-col leading-tight sm:flex">
              <span className="text-lg font-extrabold tracking-tight text-brand-900">CAVAT</span>
              <span className="text-xs text-slate-600">Gia sư AI · Toán lớp 5</span>
            </span>
          </Link>
          <RoleSwitcher current={current} />
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

function RoleSwitcher({ current }: { current: AccountKind | null }) {
  const { user, accounts, switchTo, loggedIn, changeStudent, studentSignup } = useAuth();
  const navigate = useNavigate();
  const [asking, setAsking] = useState<AccountKind | null>(null);
  const nameOf = (kind: AccountKind) => accounts.find((a) => a.kind === kind)?.display_name;

  const open = (kind: AccountKind) => {
    if (kind === current) return void navigate(homeOf(kind));
    if (!user || switchTo(kind)) return void navigate(homeOf(kind));
    setAsking(kind);
  };

  return (
    <>
      <nav aria-label="Vai trò" className="flex items-center gap-1 rounded-full bg-slate-100 p-1">
        {ROLES.map((kind) => {
          const active = kind === current;
          return (
            <button
              key={kind}
              type="button"
              aria-current={active ? "page" : undefined}
              onClick={() => open(kind)}
              title={nameOf(kind) ? `${ROLE_LABEL[kind]}: ${nameOf(kind)}` : ROLE_LABEL[kind]}
              className={`min-h-11 shrink-0 rounded-full px-3 text-sm font-semibold transition sm:px-4 ${
                active ? ROLE_TONE[kind] : "text-slate-700 hover:bg-white"
              }`}
            >
              {ROLE_LABEL[kind]}
            </button>
          );
        })}
      </nav>
      {studentSignup && (user?.kind === "STUDENT" || user?.kind === "PARENT") && (
        <button
          type="button"
          onClick={() => {
            changeStudent();
            void navigate("/");
          }}
          title={`Đang dùng: ${user.display_name}`}
          className="min-h-11 shrink-0 rounded-full px-3 text-sm font-semibold text-slate-700 hover:bg-slate-100"
        >
          Đổi tài khoản
        </button>
      )}
      {asking && (
        <PinDialog
          kind={asking}
          studentSignup={studentSignup}
          account={accounts.find((a) => a.kind === asking)}
          onClose={() => setAsking(null)}
          onDone={(kind) => {
            setAsking(null);
            loggedIn();
            void navigate(homeOf(kind));
          }}
        />
      )}
    </>
  );
}

function PinDialog({
  kind,
  account,
  onClose,
  onDone,
  studentSignup,
}: {
  studentSignup: boolean;
  kind: AccountKind;
  account: { kind: AccountKind; login_name: string; display_name: string } | undefined;
  onClose: () => void;
  onDone: (kind: AccountKind) => void;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  // In the body: the header's backdrop blur would make "fixed" relative to the header.
  return createPortal(
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/40 p-4" onClick={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="switch-title"
        className="card w-full max-w-sm p-5"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="switch-title" className="text-lg font-bold">
          Mở vai {ROLE_LABEL[kind]}
        </h2>
        {(kind === "STUDENT" || kind === "PARENT") && studentSignup ? (
          <ChildForm role={kind} onLoggedIn={() => onDone(kind)} />
        ) : account ? (
          <>
            <p className="mt-1 text-sm text-slate-600">
              Lần đầu mở vai này trên máy, nhập mã PIN của {account.display_name}. Lần sau chỉ cần bấm.
            </p>
            <PinForm accounts={[account]} onLoggedIn={() => onDone(kind)} />
          </>
        ) : (
          <p className="mt-2 text-sm">
            Chưa có tài khoản {ROLE_LABEL[kind].toLowerCase()}. Tạo bằng lệnh <code>make accounts</code>.
          </p>
        )}
        <button
          type="button"
          onClick={onClose}
          className="mt-3 min-h-11 w-full rounded-xl px-4 text-sm font-semibold text-slate-700 hover:bg-slate-100"
        >
          Đóng
        </button>
      </section>
    </div>,
    document.body,
  );
}
