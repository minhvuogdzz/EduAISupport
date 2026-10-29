import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate } from "react-router";

import type { AccountKind } from "../api/contract";
import { ChildForm, PinForm } from "../features/auth/AuthGate";
import { homeOf, ROLE_LABEL, ROLES, roleOfPath, useAuth } from "../features/auth/authContext";
import { MockBanner } from "./MockBanner";
import { PageMotion } from "./PageMotion";
import { ArrowUpIcon, MailIcon, MapPinIcon, PhoneIcon, UserIcon } from "./icons";

/** Each role has its colour, so the screen says at a glance whose area it is (ACC-2). */
const ROLE_TONE: Record<AccountKind, string> = {
  STUDENT: "role-active",
  PARENT: "role-active",
  TEACHER: "role-active",
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
  const current = pathname === "/admin" ? null : (user?.kind ?? roleOfPath(pathname));
  const landing = pathname === "/";
  const [showBackToTop, setShowBackToTop] = useState(false);

  useEffect(() => {
    const update = () => setShowBackToTop(window.scrollY > 480);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);

  const backToTop = () => {
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
  };
  return (
    <PageMotion pageKey={pathname}>
      <div
        className={`site-shell ${landing ? "public-site" : "workspace-site"} ${pathname === "/admin" ? "admin-site" : ""}`}
      >
        <MockBanner />
        <a className="skip-link" href="#main-content">
          Đến nội dung chính
        </a>
        <header className="site-header">
          <div className="header-inner">
            <Link to="/" className="wordmark" aria-label="Monkey Edu, trang chủ">
              <img className="wordmark-buddy" src="/favicon.svg" width="43" height="43" alt="" />
              <span>
                monkey<span className="wordmark-light">edu</span>
                <small>Học chậm một chút. Hiểu sâu hơn.</small>
              </span>
            </Link>
            {landing && (
              <nav aria-label="Điều hướng nhanh" className="public-nav">
                <a href="#learning">Cách học</a>
                <a href="#benefits">Lợi ích</a>
                <a href="#comparison">Điểm khác biệt</a>
                <a href="#buddy">Monkey Buddy</a>
              </nav>
            )}
            <div className="header-account">
              <RoleSwitcher current={current} />
            </div>
          </div>
          <div className="reading-progress" aria-hidden="true" />
        </header>
        <main
          id="main-content"
          className={
            landing ? "landing-page" : `workspace-page workspace-${current?.toLowerCase() ?? "guest"}`
          }
        >
          {children}
        </main>
        <footer className="site-footer">
          <div className="footer-top">
            <div className="footer-intro">
              <Link to="/" className="footer-brand">
                monkeyedu<span>.</span>
              </Link>
              <p>
                Mỗi điều hiểu được,
                <br />
                là một bước tự tin hơn.
              </p>
            </div>
            <div className="footer-contacts" aria-label="Thông tin liên hệ">
              <section className="footer-contact-card">
                <MailIcon />
                <div>
                  <h2>Hỗ trợ khẩn cấp</h2>
                  <a href="mailto:ougvn.it2@gmail.com">ougvn.it2@gmail.com</a>
                </div>
              </section>
              <section className="footer-contact-card">
                <MailIcon />
                <div>
                  <h2>Nhà phát hành</h2>
                  <a href="mailto:devhousesoftware.inc@gmail.com">devhousesoftware.inc@gmail.com</a>
                </div>
              </section>
              <section className="footer-contact-card">
                <PhoneIcon />
                <div>
                  <h2>Hotline</h2>
                  <a href="tel:+84869528304">0869 528 304</a>
                </div>
              </section>
              <section className="footer-contact-card">
                <MapPinIcon />
                <div>
                  <h2>Văn phòng</h2>
                  <address>324 Thụy Khuê, P. Tây Hồ, TP. Hà Nội</address>
                </div>
              </section>
            </div>
          </div>
          <div className="footer-bottom">
            <span>© 2026 Monkey Edu · Devhouse Software</span>
            <nav aria-label="Liên kết cuối trang">
              <Link to="/student">Học sinh</Link>
              <Link to="/parent">Phụ huynh</Link>
              <Link to="/teacher">Giáo viên</Link>
            </nav>
            <span>Cùng con tìm ra cách làm.</span>
          </div>
        </footer>
        {showBackToTop && (
          <button
            type="button"
            className="back-to-top"
            onClick={backToTop}
            aria-label="Quay lại đầu trang"
            title="Lên đầu trang"
          >
            <ArrowUpIcon />
          </button>
        )}
      </div>
    </PageMotion>
  );
}

function RoleSwitcher({ current }: { current: AccountKind | null }) {
  const { user, accounts, switchTo, loggedIn, changeStudent, studentSignup } = useAuth();
  const navigate = useNavigate();
  const [asking, setAsking] = useState<AccountKind | null>(null);
  const { pathname } = useLocation();
  const nameOf = (kind: AccountKind) => accounts.find((a) => a.kind === kind)?.display_name;

  const open = (kind: AccountKind) => {
    if (kind === current) return void navigate(homeOf(kind));
    if (!user || switchTo(kind)) return void navigate(homeOf(kind));
    setAsking(kind);
  };

  return (
    <>
      <nav aria-label="Vai trò" className="role-nav">
        {ROLES.map((kind) => {
          const active = kind === current;
          return (
            <button
              key={kind}
              type="button"
              aria-current={active ? "page" : undefined}
              onClick={() => open(kind)}
              title={nameOf(kind) ? `${ROLE_LABEL[kind]}: ${nameOf(kind)}` : ROLE_LABEL[kind]}
              className={`role-link ${active ? ROLE_TONE[kind] : ""}`}
            >
              {ROLE_LABEL[kind]}
            </button>
          );
        })}
        <Link
          to="/admin"
          className="role-link admin-nav"
          aria-current={pathname === "/admin" ? "page" : undefined}
        >
          Admin
        </Link>
      </nav>
      {user && (
        <span className="account-name" title={`Tài khoản: ${user.display_name}`}>
          <UserIcon />
          <span>{user.display_name}</span>
        </span>
      )}
      {studentSignup && (user?.kind === "STUDENT" || user?.kind === "PARENT") && (
        <button
          type="button"
          onClick={() => {
            changeStudent();
            void navigate("/student");
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

export function PinDialog({
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
