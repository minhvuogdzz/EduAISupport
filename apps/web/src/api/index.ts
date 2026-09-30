import type { SessionApi } from "./client";
import { createMockApi } from "./mock/mockApi";

/**
 * The API the app talks to. Only the in-browser mock exists until T08 ships the session API; then add
 * an HTTP implementation of SessionApi here and pick it with an env flag (apps/web/README.md).
 */
export function createApi(): SessionApi {
  return createMockApi();
}
