import { createContext, useContext } from "react";

import type { AccountKind, AuthConfig, AuthUser } from "../../api/contract";

/**
 * The current account (ACC-1) and the switch between the trial's three roles (ACC-2). With the mock API or
 * the demo mode `user` is null, there is no account and switching a role only opens that role's area.
 */
export interface AuthState {
  user: AuthUser | null;
  /** The trial's accounts (accounts mode); empty without accounts. */
  accounts: AuthConfig["accounts"];
  /** Makes this role current with its kept login. False: it never logged in on this device, a PIN is needed. */
  switchTo: (kind: AccountKind) => boolean;
  /** After a PIN login from the role switcher: the new account is current, every query starts again. */
  loggedIn: () => void;
}

export const AuthContext = createContext<AuthState>({
  user: null,
  accounts: [],
  switchTo: () => true,
  loggedIn: () => {},
});

export function useAuth(): AuthState {
  return useContext(AuthContext);
}

export const ROLES: readonly AccountKind[] = ["STUDENT", "PARENT", "TEACHER"];

export const ROLE_LABEL: Record<AccountKind, string> = {
  STUDENT: "Học sinh",
  PARENT: "Phụ huynh",
  TEACHER: "Giáo viên",
};

export function homeOf(kind: AccountKind): string {
  return kind === "STUDENT" ? "/student" : kind === "PARENT" ? "/parent" : "/teacher";
}

/** The role whose area a path belongs to (the demo mode has no account to say it). */
export function roleOfPath(path: string): AccountKind | null {
  if (path.startsWith("/student")) return "STUDENT";
  if (path.startsWith("/parent")) return "PARENT";
  if (path.startsWith("/teacher")) return "TEACHER";
  return null;
}
