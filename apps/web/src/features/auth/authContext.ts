import { createContext, useContext } from "react";

import type { AccountKind, AuthUser } from "../../api/contract";

/** The logged-in account (ACC-1); null with the mock API or the demo mode, where anyone may play any role. */
export interface AuthState {
  user: AuthUser | null;
  logout: () => void;
}

export const AuthContext = createContext<AuthState>({ user: null, logout: () => {} });

export function useAuth(): AuthState {
  return useContext(AuthContext);
}

export function homeOf(kind: AccountKind): string {
  return kind === "STUDENT" ? "/student" : kind === "PARENT" ? "/parent" : "/teacher";
}
