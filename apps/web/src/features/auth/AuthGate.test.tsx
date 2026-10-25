import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiError, type SessionApi } from "../../api/client";
import type { AccountKind, AuthConfig, AuthUser } from "../../api/contract";
import { renderApp, testApi } from "../../test/renderApp";

const CONFIG: AuthConfig = {
  mode: "accounts",
  student_signup: true,
  accounts: [
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
function accountsApi(loggedIn: string | null = null): SessionApi & { logins: string[]; signIns: string[] } {
  const kept = new Map<AccountKind, AuthUser>();
  let current: AuthUser | null = loggedIn ? USERS[loggedIn] : null;
  if (current) kept.set(current.kind, current);
  const logins: string[] = [];
  const signIns: string[] = [];
  return {
    ...testApi(),
    logins,
    signIns,
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
      signInStudent: (name) => {
        signIns.push(name);
        // The same name finds the same student again (the server keys it without accents or capitals).
        const key = name.trim().toLowerCase();
        const user: AuthUser = {
          user_id: `u-${key}`,
          kind: "STUDENT",
          display_name: name.trim().split(" ").at(-1)!,
          child_id: null,
        };
        current = user;
        kept.set("STUDENT", user);
        return Promise.resolve(user);
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
  it("asks a student for the name, and a parent for the PIN", async () => {
    const api = accountsApi();
    const { user } = renderApp("/student", api);
    expect(await screen.findByRole("heading", { name: "CAVAT · Gia sư Toán lớp 5" })).toBeInTheDocument();
    for (const role of ["Học sinh", "Phụ huynh", "Giáo viên"])
      expect(screen.getByText(role)).toBeInTheDocument();

    // The student role is open at first: a name, no PIN.
    expect(screen.queryByLabelText("Mã PIN")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vào học" })).toBeDisabled();
    await user.type(screen.getByLabelText(/^Tên của con/), "Nguyễn Bảo An");
    await user.click(screen.getByRole("button", { name: "Vào học" }));
    expect(await screen.findByRole("heading", { level: 1, name: /Chào An/ })).toBeInTheDocument();
    expect(api.signIns).toEqual(["Nguyễn Bảo An"]);
    const roles = screen.getByRole("navigation", { name: "Vai trò" });
    expect(within(roles).getByRole("button", { name: "Học sinh" })).toHaveAttribute("aria-current", "page");
  });

  it("refuses a wrong PIN for the parent and opens the parent's area with the right one", async () => {
    const { user } = renderApp("/parent", accountsApi());
    await user.click(await screen.findByText("Phụ huynh"));
    await user.type(screen.getByLabelText("Mã PIN"), "1111");
    await user.click(screen.getByRole("button", { name: "Mở" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Mã PIN chưa đúng.");
    await user.clear(screen.getByLabelText("Mã PIN"));
    await user.type(screen.getByLabelText("Mã PIN"), "2468");
    await user.click(screen.getByRole("button", { name: "Mở" }));
    const roles = await screen.findByRole("navigation", { name: "Vai trò" });
    expect(within(roles).getByRole("button", { name: "Phụ huynh" })).toHaveAttribute("aria-current", "page");
  });

  it("lets another child take the device: 'Đổi bạn khác' forgets the student, not the other roles", async () => {
    const api = accountsApi("hocsinh");
    const { user } = renderApp("/student", api);
    await user.click(await screen.findByRole("button", { name: "Đổi bạn khác" }));
    expect(await screen.findByLabelText(/^Tên của con/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Tên của con/), "Trần Bình");
    await user.click(screen.getByRole("button", { name: "Vào học" }));
    expect(await screen.findByRole("heading", { level: 1, name: /Chào Bình/ })).toBeInTheDocument();
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
