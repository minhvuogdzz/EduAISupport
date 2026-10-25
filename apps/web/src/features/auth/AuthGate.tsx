import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Navigate, useNavigate } from "react-router";

import { useApi } from "../../api/apiContext";
import { ApiError } from "../../api/client";
import type { AccountKind, AuthConfig, AuthUser } from "../../api/contract";
import { Mascot } from "../../components/Mascot";
import { AuthContext, homeOf, ROLE_LABEL, useAuth } from "./authContext";

/**
 * The login of the trial's three accounts (ACC-1). With the real API in accounts mode, nothing is shown
 * until one of them logs in with a PIN; the mock API and the demo mode keep the app open as before.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const api = useApi();
  const queryClient = useQueryClient();
  const config = useQuery({
    queryKey: ["auth-config"],
    queryFn: () => api.auth!.config(),
    enabled: api.auth !== undefined,
    retry: false,
  });
  const accounts = config.data?.mode === "accounts";
  const me = useQuery({
    queryKey: ["auth-me"],
    queryFn: () => api.auth!.me(),
    enabled: accounts,
    retry: false,
  });

  if (!api.auth || config.data?.mode === "demo") {
    return <AuthContext.Provider value={NO_ACCOUNTS}>{children}</AuthContext.Provider>;
  }
  if (config.isPending || (accounts && me.isPending)) {
    return <Centered>Đang mở…</Centered>;
  }
  if (config.isError) {
    return <Centered>Chưa kết nối được máy chủ. Hãy chạy bản demo bằng lệnh make demo.</Centered>;
  }
  if (me.isError || !me.data) {
    return <LoginPage config={config.data} />;
  }
  // Another role's data must never show under this one: every query starts again for the new account.
  const restart = () => void queryClient.resetQueries();
  const state = {
    user: me.data,
    accounts: config.data.accounts,
    studentSignup: config.data.student_signup === true,
    switchTo: (kind: AccountKind) => {
      if (kind === me.data.kind) return true;
      if (!api.auth!.switchTo(kind)) return false;
      restart();
      return true;
    },
    loggedIn: () => restart(),
    changeStudent: () => {
      api.auth!.logout();
      queryClient.removeQueries({ queryKey: ["auth-me"] });
      restart();
    },
  };
  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

const NO_ACCOUNTS = {
  user: null,
  accounts: [],
  studentSignup: false,
  switchTo: () => true,
  loggedIn: () => {},
  changeStudent: () => {},
};

/** Only the account of this kind sees the page; another account is sent to its own home. */
export function RequireKind({ kind, children }: { kind: AccountKind; children: ReactNode }) {
  const { user } = useAuth();
  if (user && user.kind !== kind) return <Navigate to={homeOf(user.kind)} replace />;
  return <>{children}</>;
}

function Centered({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-paper p-6">
      <p role="status" className="card max-w-md p-6 text-center">
        {children}
      </p>
    </main>
  );
}

function LoginPage({ config }: { config: AuthConfig }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const signup = config.student_signup === true;
  // The students come in by name; the parent and the teacher keep their PIN.
  const roles: AccountKind[] = [
    ...(signup ? (["STUDENT"] as const) : []),
    ...config.accounts.map((a) => a.kind).filter((kind) => kind !== "STUDENT" || !signup),
  ];
  const [role, setRole] = useState<AccountKind | null>(signup ? "STUDENT" : null);
  const account = config.accounts.find((a) => a.kind === role);
  const onLoggedIn = (user: AuthUser) => {
    queryClient.setQueryData(["auth-me"], user);
    void navigate(homeOf(user.kind));
  };
  return (
    <main className="flex min-h-dvh items-center justify-center bg-paper p-4">
      <title>Đăng nhập · CAVAT</title>
      <section className="card brand-gradient w-full max-w-lg p-6" aria-labelledby="login-title">
        <div className="flex items-center gap-3">
          <Mascot size={56} />
          <div>
            <h1 id="login-title" className="text-xl font-extrabold">
              CAVAT · Gia sư Toán lớp 5
            </h1>
            <p className="text-sm text-slate-700">Chọn vai trò của bạn.</p>
          </div>
        </div>
        {roles.length === 0 ? (
          <p role="status" className="mt-4 rounded-2xl bg-white/80 p-4 text-sm">
            Chưa có tài khoản nào. Tạo phụ huynh và giáo viên bằng lệnh{" "}
            <code className="font-mono">make accounts</code>.
          </p>
        ) : (
          <>
            <fieldset className="mt-4 grid gap-2 sm:grid-cols-3">
              <legend className="sr-only">Vai trò</legend>
              {roles.map((kind) => (
                <label
                  key={kind}
                  className={`cursor-pointer rounded-2xl bg-white p-3 text-center ring-1 ${
                    role === kind ? "ring-2 ring-brand-600" : "ring-slate-200 hover:ring-brand-300"
                  }`}
                >
                  <input
                    type="radio"
                    name="role"
                    className="sr-only"
                    checked={role === kind}
                    onChange={() => setRole(kind)}
                  />
                  <span className="block font-semibold">{ROLE_LABEL[kind]}</span>
                </label>
              ))}
            </fieldset>
            {role === "STUDENT" && signup && <StudentNameForm onLoggedIn={onLoggedIn} />}
            {role && role !== "STUDENT" && account && (
              <PinForm key={role} accounts={[account]} onLoggedIn={onLoggedIn} />
            )}
          </>
        )}
      </section>
    </main>
  );
}

/**
 * A student comes in by typing their name: the first time makes the account, later times (a crash, another
 * device) find the same student and the same history again. There is no PIN for children.
 */
export function StudentNameForm({ onLoggedIn }: { onLoggedIn: (user: AuthUser) => void }) {
  const api = useApi();
  const [name, setName] = useState("");
  const signIn = useMutation({
    mutationFn: () => api.auth!.signInStudent(name.trim()),
    onSuccess: onLoggedIn,
  });
  return (
    <form
      className="mt-4 flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (name.trim()) signIn.mutate();
      }}
    >
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-semibold">Tên của con</span>
        <input
          type="text"
          autoComplete="off"
          autoFocus
          maxLength={40}
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Ví dụ: Nguyễn Bảo An"
          className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-lg focus:border-brand-600"
        />
        <span className="text-xs text-slate-600">
          Lần sau con gõ đúng tên này để học tiếp, cô vẫn nhớ con học đến đâu.
        </span>
      </label>
      {signIn.isError && (
        <p role="alert" className="text-sm font-medium text-rose-700">
          Chưa vào được. Con kiểm tra lại tên rồi thử lại nhé.
        </p>
      )}
      <button
        type="submit"
        disabled={!name.trim() || signIn.isPending}
        className="rounded-xl bg-brand-700 px-4 py-2.5 font-semibold text-white hover:bg-brand-800 disabled:opacity-50"
      >
        Vào học
      </button>
    </form>
  );
}

/**
 * The PIN of one of the accounts: the login page offers all three, the role switcher (ACC-2) only the role
 * the user picked, the first time that role is opened on this device.
 */
export function PinForm({
  accounts,
  onLoggedIn,
}: {
  accounts: AuthConfig["accounts"];
  onLoggedIn: (user: AuthUser) => void;
}) {
  const api = useApi();
  const [chosen, setChosen] = useState<AuthConfig["accounts"][number] | null>(
    accounts.length === 1 ? accounts[0] : null,
  );
  const [pin, setPin] = useState("");
  const login = useMutation({
    mutationFn: () => api.auth!.login(chosen!.login_name, pin),
    onSuccess: onLoggedIn,
  });
  const error =
    login.error instanceof ApiError && login.error.status === 429
      ? "Nhập sai nhiều lần quá, đợi 5 phút rồi thử lại nhé."
      : login.isError
        ? "Mã PIN chưa đúng."
        : null;
  return (
    <form
      className="mt-4 flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (chosen && pin) login.mutate();
      }}
    >
      {accounts.length > 1 && (
        <fieldset className="grid gap-2 sm:grid-cols-3">
          <legend className="sr-only">Tài khoản</legend>
          {accounts.map((account) => (
            <label
              key={account.login_name}
              className={`cursor-pointer rounded-2xl bg-white p-3 text-center ring-1 ${
                chosen?.login_name === account.login_name
                  ? "ring-2 ring-brand-600"
                  : "ring-slate-200 hover:ring-brand-300"
              }`}
            >
              <input
                type="radio"
                name="account"
                className="sr-only"
                checked={chosen?.login_name === account.login_name}
                onChange={() => setChosen(account)}
              />
              <span className="block text-xs text-slate-500">{ROLE_LABEL[account.kind]}</span>
              <span className="block font-semibold">{account.display_name}</span>
            </label>
          ))}
        </fieldset>
      )}
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-semibold">Mã PIN</span>
        <input
          type="password"
          inputMode="numeric"
          autoComplete="current-password"
          autoFocus={accounts.length === 1}
          maxLength={8}
          value={pin}
          onChange={(event) => setPin(event.target.value.replace(/\D/g, ""))}
          className="rounded-xl border border-slate-300 bg-white px-3 py-2 font-mono text-lg tracking-[0.3em] focus:border-brand-600"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm font-medium text-rose-700">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={!chosen || pin.length < 4 || login.isPending}
        className="rounded-xl bg-brand-700 px-4 py-2.5 font-semibold text-white hover:bg-brand-800 disabled:opacity-50"
      >
        {accounts.length === 1 ? "Mở" : "Đăng nhập"}
      </button>
    </form>
  );
}
