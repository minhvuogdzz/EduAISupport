const KEY = "cavat.student.last-session";

/** Remembers the student's session on this device, so the start page can offer "Học tiếp". */
export function rememberSession(sessionId: string, key = KEY) {
  try {
    localStorage.setItem(key, sessionId);
  } catch {
    // storage unavailable: the student simply starts a new demo session next time
  }
}

export function readLastSessionId(key = KEY): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
