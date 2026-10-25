import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ChangeEvent, type ReactNode } from "react";
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
  // A child's account serves the student and the parent; the teacher is the fixed account with its PIN.
  const hasTeacher = config.accounts.some((a) => a.kind === "TEACHER");
  const roles: AccountKind[] = signup
    ? ["STUDENT", "PARENT", ...(hasTeacher ? (["TEACHER"] as const) : [])]
    : config.accounts.map((a) => a.kind);
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
            {signup && (role === "STUDENT" || role === "PARENT") && (
              <ChildForm key={role} role={role} onLoggedIn={onLoggedIn} />
            )}
            {role && !(signup && (role === "STUDENT" || role === "PARENT")) && account && (
              <PinForm key={role} accounts={[account]} onLoggedIn={onLoggedIn} />
            )}
          </>
        )}
      </section>
    </main>
  );
}

/**
 * A child's account: a username and a passcode. The first time the child makes it ("Tạo tài khoản mới"),
 * later times they type the same pair, on any device. The parent opens the same account (role PARENT), so
 * the parent types the child's pair too. The old trial student opens with its name and old PIN.
 */
export function ChildForm({
  role,
  onLoggedIn,
}: {
  role: "STUDENT" | "PARENT";
  onLoggedIn: (user: AuthUser) => void;
}) {
  const api = useApi();
  const [creating, setCreating] = useState(false);
  const [username, setUsername] = useState("");
  const [passcode, setPasscode] = useState("");
  const [again, setAgain] = useState("");
  const mismatch = creating && again !== "" && again !== passcode;
  const enter = useMutation({
    mutationFn: () =>
      creating
        ? api.auth!.register(username.trim(), passcode)
        : api.auth!.login(username.trim(), passcode, role),
    onSuccess: onLoggedIn,
  });
  const status = enter.error instanceof ApiError ? enter.error.status : null;
  const error = !enter.isError
    ? null
    : status === 429
      ? "Nhập sai nhiều lần quá, đợi 5 phút rồi thử lại nhé."
      : status === 409
        ? "Tên đăng nhập này có bạn khác dùng rồi. Con chọn tên khác nhé."
        : status === 422
          ? "Tên đăng nhập cần có chữ, mã bí mật gồm 4 đến 8 chữ số."
          : creating
            ? "Chưa tạo được tài khoản. Con thử lại nhé."
            : "Tên đăng nhập hoặc mã bí mật chưa đúng.";
  const ready =
    username.trim() !== "" && passcode.length >= 4 && (!creating || again === passcode) && !enter.isPending;
  const digits = (set: (value: string) => void) => (event: ChangeEvent<HTMLInputElement>) =>
    set(event.target.value.replace(/\D/g, ""));
  return (
    <form
      className="mt-4 flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) enter.mutate();
      }}
    >
      {role === "PARENT" && (
        <p className="text-sm text-slate-700">
          Phụ huynh dùng chung tài khoản với con: nhập tên và mã của con.
        </p>
      )}
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-semibold">Tên đăng nhập</span>
        <input
          type="text"
          autoComplete="username"
          autoFocus
          maxLength={40}
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="Ví dụ: Bảo An"
          className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-lg focus:border-brand-600"
        />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-semibold">{creating ? "Tạo mã bí mật" : "Mã bí mật"}</span>
        <input
          type="password"
          inputMode="numeric"
          autoComplete={creating ? "new-password" : "current-password"}
          maxLength={8}
          value={passcode}
          onChange={digits(setPasscode)}
          className="rounded-xl border border-slate-300 bg-white px-3 py-2 font-mono text-lg tracking-[0.3em] focus:border-brand-600"
        />
      </label>
      {creating && (
        <span className="text-xs text-slate-600">Từ 4 đến 8 chữ số. Con nhớ mã này để vào lần sau.</span>
      )}
      {creating && (
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold">Nhập lại mã bí mật</span>
          <input
            type="password"
            inputMode="numeric"
            autoComplete="new-password"
            maxLength={8}
            value={again}
            onChange={digits(setAgain)}
            className="rounded-xl border border-slate-300 bg-white px-3 py-2 font-mono text-lg tracking-[0.3em] focus:border-brand-600"
          />
        </label>
      )}
      {(error || mismatch) && (
        <p role="alert" className="text-sm font-medium text-rose-700">
          {mismatch ? "Hai lần nhập mã chưa giống nhau." : error}
        </p>
      )}
      <button
        type="submit"
        disabled={!ready}
        className="rounded-xl bg-brand-700 px-4 py-2.5 font-semibold text-white hover:bg-brand-800 disabled:opacity-50"
      >
        {creating ? "Tạo tài khoản và vào học" : role === "PARENT" ? "Mở" : "Vào học"}
      </button>
      {role === "STUDENT" && (
        <button
          type="button"
          onClick={() => {
            setCreating(!creating);
            enter.reset();
          }}
          className="min-h-11 rounded-xl text-sm font-semibold text-brand-800 hover:bg-white/60"
        >
          {creating ? "Mình đã có tài khoản" : "Lần đầu học? Tạo tài khoản mới"}
        </button>
      )}
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
