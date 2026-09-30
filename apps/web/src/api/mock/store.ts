import type { CommandAck } from "../contract";
import type { MockSession } from "./engine";

/** Everything the mock "server" keeps: sessions (state + events) and processed idempotency keys. */
export interface MockDb {
  schema: 1;
  sessions: Record<string, MockSession>;
  /** `${session_id}:${idempotency_key}` → the ack returned the first time. */
  acks: Record<string, CommandAck>;
}

export interface MockStore {
  /** null when nothing is stored yet (first visit, or after a reset). */
  read(): MockDb | null;
  write(db: MockDb): void;
  clear(): void;
}

const STORAGE_KEY = "cavat.mock-api.v1";

/** localStorage when usable, so a teacher tab sees what a student tab did; else memory only. */
export function browserStorage(): Storage | null {
  try {
    const storage = globalThis.localStorage;
    storage.setItem(`${STORAGE_KEY}.probe`, "1");
    storage.removeItem(`${STORAGE_KEY}.probe`);
    return storage;
  } catch {
    return null; // private mode, blocked site data, no DOM
  }
}

export function createStore(storage: Storage | null): MockStore {
  let memory: string | null = null;
  let useStorage = storage !== null;

  function load(): string | null {
    if (useStorage && storage) {
      try {
        return storage.getItem(STORAGE_KEY);
      } catch {
        useStorage = false;
      }
    }
    return memory;
  }

  function save(raw: string | null) {
    memory = raw;
    if (!useStorage || !storage) return;
    try {
      if (raw === null) storage.removeItem(STORAGE_KEY);
      else storage.setItem(STORAGE_KEY, raw);
    } catch {
      useStorage = false; // quota exceeded or storage revoked: carry on in memory
    }
  }

  return {
    read() {
      const raw = load();
      if (!raw) return null;
      try {
        const db = JSON.parse(raw) as Partial<MockDb> | null;
        const valid = db?.schema === 1 && typeof db.sessions === "object" && typeof db.acks === "object";
        return valid ? (db as MockDb) : null;
      } catch {
        return null;
      }
    },
    write(db) {
      save(JSON.stringify(db));
    },
    clear() {
      save(null);
    },
  };
}
