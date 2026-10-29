import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiError, type SessionApi } from "../../api/client";
import type { AccountKind, AuthConfig, AuthUser } from "../../api/contract";
import { renderApp, testApi } from "../../test/renderApp";

const CONFIG: AuthConfig = {
  mode: "accounts",
  student_signup: true,
  accounts: [{ kind: "TEACHER", login_name: "giaovien", display_name: "Cô Lan" }],
};

const TEACHER: AuthUser = { user_id: "u-t", kind: "TEACHER", display_name: "Cô Lan", child_id: null };
const OLD_STUDENT: AuthUser = { user_id: "u-old", kind: "STUDENT", display_name: "Vuong", child_id: null };

/**
 * The mock API with the accounts: the teacher (PIN 2468), the old student "vuong" (PIN 2468) and the children
 * who register. Like the real client, it keeps the login of each role (ACC-2); a child's login also keeps the
 * parent role of the same account. `logins` counts the sign-ins typed.
 */
function accountsApi(loggedIn: "teacher" | null = null): SessionApi & { logins: string[] } {
  const accounts = new Map<string, { user: AuthUser; code: string }>([
    ["giaovien", { user: TEACHER, code: "2468" }],
    ["vuong", { user: OLD_STUDENT, code: "2468" }],
  ]);
  const kept = new Map<AccountKind, AuthUser>();
  let current: AuthUser | null = loggedIn ? TEACHER : null;
  if (current) kept.set(current.kind, current);
  const logins: string[] = [];
  const parentOf = (child: AuthUser): AuthUser => ({
    user_id: child.user_id,
    kind: "PARENT",
    display_name: `Phụ huynh của ${child.display_name}`,
    child_id: child.user_id,
  });
  const enter = (user: AuthUser, role?: AccountKind): AuthUser => {
    if (user.kind === "STUDENT") kept.set("PARENT", parentOf(user));
    const shown = user.kind === "STUDENT" && role === "PARENT" ? parentOf(user) : user;
    kept.set(shown.kind, shown);
    current = shown;
    return shown;
  };
  return {
    ...testApi(),
    logins,
    auth: {
      config: () => Promise.resolve(CONFIG),
      login: (name, pin, role) => {
        logins.push(name);
        const found = accounts.get(name.trim().toLowerCase());
        if (!found || found.code !== pin) {
          return Promise.reject(new ApiError(401, "NOT_SESSION_OWNER", "wrong"));
        }
        return Promise.resolve(enter(found.user, role));
      },
      register: (username, passcode) => {
        const key = username.trim().toLowerCase();
        if (accounts.has(key)) return Promise.reject(new ApiError(409, "INVALID_STATE", "taken"));
        const user: AuthUser = {
          user_id: `u-${key}`,
          kind: "STUDENT",
          display_name: username.trim().split(" ").at(-1)!,
          child_id: null,
        };
        accounts.set(key, { user, code: passcode });
        return Promise.resolve(enter(user));
      },
      me: () =>
        current ? Promise.resolve(current) : Promise.reject(new ApiError(401, "NOT_SESSION_OWNER", "log in")),
      switchTo: (kind) => {
        const user = kept.get(kind);
        if (user) current = user;
        return user !== undefined;
      },
      logout: () => {
        if (current) {
          const child = current.kind === "STUDENT" || current.kind === "PARENT";
          kept.delete(current.kind);
          if (child) {
            kept.delete("STUDENT");
            kept.delete("PARENT");
          }
        }
        current = null;
      },
    },
  };
}

const rolesNav = () => screen.findByRole("navigation", { name: "Vai trò" });

describe("accounts: children make their own, the parent shares it, the teacher is fixed", () => {
  it("makes a child's account with a username and a passcode written twice", async () => {
    const { user } = renderApp("/student", accountsApi());
    expect(await screen.findByRole("heading", { name: "Mình vào học nhé." })).toBeInTheDocument();
    for (const role of ["Học sinh", "Phụ huynh", "Giáo viên"])
      expect(screen.getByText(role)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Lần đầu học? Tạo tài khoản mới" }));
    const submit = screen.getByRole("button", { name: "Tạo tài khoản và vào học" });
    await user.type(screen.getByLabelText("Tên đăng nhập"), "Nguyễn Bảo An");
    await user.type(screen.getByLabelText("Tạo mã bí mật"), "4321");
    await user.type(screen.getByLabelText("Nhập lại mã bí mật"), "4300");
    expect(await screen.findByRole("alert")).toHaveTextContent("Hai lần nhập mã chưa giống nhau.");
    expect(submit).toBeDisabled();
    await user.clear(screen.getByLabelText("Nhập lại mã bí mật"));
    await user.type(screen.getByLabelText("Nhập lại mã bí mật"), "4321");
    await user.click(submit);

    expect(await screen.findByRole("heading", { level: 1, name: /Chào An/ })).toBeInTheDocument();
    const roles = await rolesNav();
    expect(within(roles).getByRole("button", { name: "Học sinh" })).toHaveAttribute("aria-current", "page");
  });

  it("refuses a taken username and says to choose another", async () => {
    const { user } = renderApp("/student", accountsApi());
    await user.click(await screen.findByRole("button", { name: "Lần đầu học? Tạo tài khoản mới" }));
    await user.type(screen.getByLabelText("Tên đăng nhập"), "Vuong");
    await user.type(screen.getByLabelText("Tạo mã bí mật"), "4321");
    await user.type(screen.getByLabelText("Nhập lại mã bí mật"), "4321");
    await user.click(screen.getByRole("button", { name: "Tạo tài khoản và vào học" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("có bạn khác dùng rồi");
  });

  it("comes back with the same username and passcode, and a wrong passcode does not open it", async () => {
    const { user } = renderApp("/student", accountsApi());
    await user.type(await screen.findByLabelText("Tên đăng nhập"), "Vuong");
    await user.type(screen.getByLabelText("Mã bí mật"), "1111");
    await user.click(screen.getByRole("button", { name: "Vào học" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("chưa đúng");
    await user.clear(screen.getByLabelText("Mã bí mật"));
    await user.type(screen.getByLabelText("Mã bí mật"), "2468");
    await user.click(screen.getByRole("button", { name: "Vào học" }));
    // The old student of the trial opens with its name and old PIN.
    expect(await screen.findByRole("heading", { level: 1, name: /Chào Vuong/ })).toBeInTheDocument();
  });

  it("opens the parent role of the same account with no second login", async () => {
    const api = accountsApi();
    const { user } = renderApp("/student", api);
    await user.type(await screen.findByLabelText("Tên đăng nhập"), "Vuong");
    await user.type(screen.getByLabelText("Mã bí mật"), "2468");
    await user.click(screen.getByRole("button", { name: "Vào học" }));
    await screen.findByRole("heading", { level: 1, name: /Chào Vuong/ });

    await user.click(within(await rolesNav()).getByRole("button", { name: "Phụ huynh" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      await within(await rolesNav()).findByRole("button", { name: "Phụ huynh", current: "page" }),
    ).toBeInTheDocument();
    expect(api.logins).toEqual(["Vuong"]);
  });

  it("opens the parent role on a new device with the child's username and passcode", async () => {
    const { user } = renderApp("/parent", accountsApi());
    await user.click(await screen.findByText("Phụ huynh"));
    expect(screen.getByText(/dùng chung tài khoản với con/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Tên đăng nhập"), "Vuong");
    await user.type(screen.getByLabelText("Mã bí mật"), "2468");
    await user.click(screen.getByRole("button", { name: "Mở" }));
    expect(
      await within(await rolesNav()).findByRole("button", { name: "Phụ huynh", current: "page" }),
    ).toBeInTheDocument();
  });

  it("keeps the teacher on the fixed PIN login", async () => {
    const { user } = renderApp("/teacher", accountsApi());
    await user.click(await screen.findByText("Giáo viên"));
    expect(screen.queryByLabelText("Tên đăng nhập")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Mã PIN"), "2468");
    await user.click(screen.getByRole("button", { name: "Mở" }));
    expect(
      await within(await rolesNav()).findByRole("button", { name: "Giáo viên", current: "page" }),
    ).toBeInTheDocument();
  });

  it("sends an account to its own area", async () => {
    renderApp("/student", accountsApi("teacher"));
    const roles = await rolesNav();
    expect(within(roles).getByRole("button", { name: "Giáo viên" })).toHaveAttribute("aria-current", "page");
  });

  it("switches to the teacher with a PIN the first time, then one click", async () => {
    const api = accountsApi();
    const { user } = renderApp("/student", api);
    await user.type(await screen.findByLabelText("Tên đăng nhập"), "Vuong");
    await user.type(screen.getByLabelText("Mã bí mật"), "2468");
    await user.click(screen.getByRole("button", { name: "Vào học" }));
    await screen.findByRole("heading", { level: 1, name: /Chào Vuong/ });

    await user.click(within(await rolesNav()).getByRole("button", { name: "Giáo viên" }));
    const dialog = await screen.findByRole("dialog", { name: "Mở vai Giáo viên" });
    await user.type(within(dialog).getByLabelText("Mã PIN"), "2468");
    await user.click(within(dialog).getByRole("button", { name: "Mở" }));
    await within(await rolesNav()).findByRole("button", { name: "Giáo viên", current: "page" });

    await user.click(within(await rolesNav()).getByRole("button", { name: "Học sinh" }));
    expect(await screen.findByRole("heading", { level: 1, name: /Chào Vuong/ })).toBeInTheDocument();
    await user.click(within(await rolesNav()).getByRole("button", { name: "Giáo viên" }));
    await within(await rolesNav()).findByRole("button", { name: "Giáo viên", current: "page" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.logins).toEqual(["Vuong", "giaovien"]);
  });

  it("lets another child take the device: 'Đổi tài khoản' forgets the child, student and parent", async () => {
    const { user } = renderApp("/student", accountsApi());
    await user.type(await screen.findByLabelText("Tên đăng nhập"), "Vuong");
    await user.type(screen.getByLabelText("Mã bí mật"), "2468");
    await user.click(screen.getByRole("button", { name: "Vào học" }));
    await user.click(await screen.findByRole("button", { name: "Đổi tài khoản" }));
    expect(await screen.findByLabelText("Tên đăng nhập")).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "Lần đầu học? Tạo tài khoản mới" }));
    await user.type(screen.getByLabelText("Tên đăng nhập"), "Trần Bình");
    await user.type(screen.getByLabelText("Tạo mã bí mật"), "5678");
    await user.type(screen.getByLabelText("Nhập lại mã bí mật"), "5678");
    await user.click(screen.getByRole("button", { name: "Tạo tài khoản và vào học" }));
    expect(await screen.findByRole("heading", { level: 1, name: /Chào Bình/ })).toBeInTheDocument();
  });

  it("keeps the mock API open without a login, as the one demo student", async () => {
    renderApp("/student", testApi());
    expect(await screen.findByRole("heading", { level: 1, name: /Chào An/ })).toBeInTheDocument();
  });
});
