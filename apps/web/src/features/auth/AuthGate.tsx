import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Navigate, useNavigate } from "react-router";

import { useApi } from "../../api/apiContext";
import { ApiError } from "../../api/client";
import type { AccountKind, AuthConfig, AuthUser } from "../../api/contract";
import { Mascot } from "../../components/Mascot";
import { AuthContext, homeOf, useAuth } from "./authContext";

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
    return <AuthContext.Provider value={{ user: null, logout: () => {} }}>{children}</AuthContext.Provider>;
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
  const logout = () => {
    api.auth?.logout();
    queryClient.removeQueries();
    void queryClient.resetQueries();
  };
  return <AuthContext.Provider value={{ user: me.data, logout }}>{children}</AuthContext.Provider>;
}

/** Only the account of this kind sees the page; another account is sent to its own home. */
export function RequireKind({ kind, children }: { kind: AccountKind; children: ReactNode }) {
  const { user } = useAuth();
  if (user && user.kind !== kind) return <Navigate to={homeOf(user.kind)} replace />;
  return <>{children}</>;
}

const KIND_LABEL: Record<AccountKind, string> = {
  STUDENT: "Học sinh",
  PARENT: "Phụ huynh",
  TEACHER: "Giáo viên",
};

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
  const api = useApi();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [chosen, setChosen] = useState<AuthConfig["accounts"][number] | null>(null);
  const [pin, setPin] = useState("");
  const login = useMutation({
    mutationFn: () => api.auth!.login(chosen!.login_name, pin),
    onSuccess: (user: AuthUser) => {
      queryClient.setQueryData(["auth-me"], user);
      void navigate(homeOf(user.kind));
    },
  });
  const error =
    login.error instanceof ApiError && login.error.status === 429
      ? "Nhập sai nhiều lần quá, đợi 5 phút rồi thử lại nhé."
      : login.isError
        ? "Mã PIN chưa đúng."
        : null;

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
            <p className="text-sm text-slate-700">Chọn tài khoản rồi nhập mã PIN.</p>
          </div>
        </div>
        {config.accounts.length === 0 ? (
          <p role="status" className="mt-4 rounded-2xl bg-white/80 p-4 text-sm">
            Chưa có tài khoản nào. Tạo một học sinh, một phụ huynh, một giáo viên bằng lệnh{" "}
            <code className="font-mono">make accounts</code>.
          </p>
        ) : (
          <form
            className="mt-4 flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (chosen && pin) login.mutate();
            }}
          >
            <fieldset className="grid gap-2 sm:grid-cols-3">
              <legend className="sr-only">Tài khoản</legend>
              {config.accounts.map((account) => (
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
                  <span className="block text-xs text-slate-500">{KIND_LABEL[account.kind]}</span>
                  <span className="block font-semibold">{account.display_name}</span>
                </label>
              ))}
            </fieldset>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-semibold">Mã PIN</span>
              <input
                type="password"
                inputMode="numeric"
                autoComplete="current-password"
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
              Đăng nhập
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
