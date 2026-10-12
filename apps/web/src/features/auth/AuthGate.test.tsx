import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiError, type SessionApi } from "../../api/client";
import type { AccountKind, AuthConfig, AuthUser } from "../../api/contract";
import { renderApp, testApi } from "../../test/renderApp";

const CONFIG: AuthConfig = {
  mode: "accounts",
  accounts: [
    { kind: "STUDENT", login_name: "hocsinh", display_name: "Minh" },
    { kind: "PARENT", login_name: "phuhuynh", display_name: "Mẹ Minh" },
    { kind: "TEACHER", login_name: "giaovien", display_name: "Cô Lan" },
  ],
};

const USERS: Record<string, AuthUser> = {
  hocsinh: { user_id: "u-s", kind: "STUDENT", display_name: "Minh", child_id: null },
  phuhuynh: { user_id: "u-p", kind: "PARENT", display_name: "Mẹ Minh", child_id: "u-s" },
  giaovien: { user_id: "u-t", kind: "TEACHER", display_name: "Cô Lan", child_id: null },
};

/**
 * The mock API with the accounts of ACC-1: PIN 2468 for everyone; `loggedIn` starts a session. Like the
 * real client, it keeps the login of each role (ACC-2); `logins` counts the PINs typed.
 */
function accountsApi(loggedIn: string | null = null): SessionApi & { logins: string[] } {
  const kept = new Map<AccountKind, AuthUser>();
  let current: AuthUser | null = loggedIn ? USERS[loggedIn] : null;
  if (current) kept.set(current.kind, current);
  const logins: string[] = [];
  return {
    ...testApi(),
    logins,
    auth: {
      config: () => Promise.resolve(CONFIG),
      login: (name, pin) => {
        logins.push(name);
        if (pin !== "2468" || !USERS[name]) {
          return Promise.reject(new ApiError(401, "NOT_SESSION_OWNER", "wrong PIN"));
        }
        current = USERS[name];
        kept.set(current.kind, current);
        return Promise.resolve(current);
      },
      me: () =>
        current ? Promise.resolve(current) : Promise.reject(new ApiError(401, "NOT_SESSION_OWNER", "log in")),
      switchTo: (kind) => {
        const user = kept.get(kind);
        if (user) current = user;
        return user !== undefined;
      },
      logout: () => {
        if (current) kept.delete(current.kind);
        current = null;
      },
    },
  };
}

describe("login of the trial accounts (ACC-1)", () => {
  it("shows the three accounts, refuses a wrong PIN and opens the student's home with the account name", async () => {
    const { user } = renderApp("/student", accountsApi());
    expect(await screen.findByRole("heading", { name: "CAVAT · Gia sư Toán lớp 5" })).toBeInTheDocument();
    for (const name of ["Minh", "Mẹ Minh", "Cô Lan"]) expect(screen.getByText(name)).toBeInTheDocument();

    await user.click(screen.getByText("Minh"));
    await user.type(screen.getByLabelText("Mã PIN"), "1111");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Mã PIN chưa đúng.");

    await user.clear(screen.getByLabelText("Mã PIN"));
    await user.type(screen.getByLabelText("Mã PIN"), "2468");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    // No name to type: the child is the account's student.
    expect(await screen.findByRole("heading", { level: 1, name: /Chào Minh/ })).toBeInTheDocument();
    expect(screen.queryByLabelText("Con tên là gì?")).not.toBeInTheDocument();
    // Nobody logs out (ACC-2): the header switches role instead.
    expect(screen.queryByRole("button", { name: "Đăng xuất" })).not.toBeInTheDocument();
    const roles = screen.getByRole("navigation", { name: "Vai trò" });
    expect(within(roles).getByRole("button", { name: "Học sinh" })).toHaveAttribute("aria-current", "page");
  });

  it("sends an account to its own area", async () => {
    renderApp("/teacher", accountsApi("phuhuynh"));
    const roles = await screen.findByRole("navigation", { name: "Vai trò" });
    expect(within(roles).getByRole("button", { name: "Phụ huynh" })).toHaveAttribute("aria-current", "page");
    expect(within(roles).getByRole("button", { name: "Giáo viên" })).not.toHaveAttribute("aria-current");
  });

  it("switches role without logging out: a PIN the first time on this device, then one click", async () => {
    const api = accountsApi("hocsinh");
    const { user } = renderApp("/student", api);
    const roles = await screen.findByRole("navigation", { name: "Vai trò" });

    await user.click(within(roles).getByRole("button", { name: "Giáo viên" }));
    const dialog = await screen.findByRole("dialog", { name: "Mở vai Giáo viên" });
    expect(dialog).toHaveTextContent("Cô Lan");
    await user.type(within(dialog).getByLabelText("Mã PIN"), "2468");
    await user.click(within(dialog).getByRole("button", { name: "Mở" }));
    expect(
      await within(await screen.findByRole("navigation", { name: "Vai trò" })).findByRole("button", {
        name: "Giáo viên",
        current: "page",
      }),
    ).toBeInTheDocument();
    expect(api.logins).toEqual(["giaovien"]);

    // Back to the student and to the teacher again: both kept, no PIN asked.
    await user.click(
      within(screen.getByRole("navigation", { name: "Vai trò" })).getByRole("button", { name: "Học sinh" }),
    );
    expect(await screen.findByRole("heading", { level: 1, name: /Chào Minh/ })).toBeInTheDocument();
    await user.click(
      within(screen.getByRole("navigation", { name: "Vai trò" })).getByRole("button", { name: "Giáo viên" }),
    );
    expect(
      await within(await screen.findByRole("navigation", { name: "Vai trò" })).findByRole("button", {
        name: "Giáo viên",
        current: "page",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.logins).toEqual(["giaovien"]);
  });

  it("keeps the mock API open without a login, as the one demo student", async () => {
    renderApp("/student", testApi());
    expect(await screen.findByRole("heading", { level: 1, name: /Chào An/ })).toBeInTheDocument();
    expect(screen.queryByLabelText("Con tên là gì?")).not.toBeInTheDocument();
  });
});
