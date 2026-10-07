import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiError, type SessionApi } from "../../api/client";
import type { AuthConfig, AuthUser } from "../../api/contract";
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
};

/** The mock API with the accounts of ACC-1: PIN 2468 for everyone; `loggedIn` starts a session. */
function accountsApi(loggedIn: string | null = null): SessionApi {
  let current = loggedIn ? USERS[loggedIn] : null;
  return {
    ...testApi(),
    auth: {
      config: () => Promise.resolve(CONFIG),
      login: (name, pin) => {
        if (pin !== "2468" || !USERS[name]) {
          return Promise.reject(new ApiError(401, "NOT_SESSION_OWNER", "wrong PIN"));
        }
        current = USERS[name];
        return Promise.resolve(current);
      },
      me: () =>
        current ? Promise.resolve(current) : Promise.reject(new ApiError(401, "NOT_SESSION_OWNER", "log in")),
      logout: () => {
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
    expect(screen.getByRole("button", { name: "Đăng xuất" })).toBeInTheDocument();
  });

  it("sends an account to its own area and shows only that area in the menu", async () => {
    renderApp("/teacher", accountsApi("phuhuynh"));
    const menu = await screen.findByRole("navigation", { name: "Vai trò" });
    expect(menu).toHaveTextContent("Phụ huynh");
    expect(menu).not.toHaveTextContent("Giáo viên");
    expect(menu).not.toHaveTextContent("Học sinh");
  });

  it("keeps the mock API open without a login", async () => {
    renderApp("/student", testApi());
    expect(await screen.findByLabelText("Con tên là gì?")).toBeInTheDocument();
  });
});
