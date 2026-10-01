const KEY = "cavat.student.last-session";

/** Remembers the student's session on this device, so the start page can offer "Học tiếp". */
export function rememberSession(sessionId: string) {
  try {
    localStorage.setItem(KEY, sessionId);
  } catch {
    // storage unavailable: the student simply starts a new demo session next time
  }
}

export function readLastSessionId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
