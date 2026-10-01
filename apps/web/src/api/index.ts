import type { SessionApi } from "./client";
import { createHttpApi } from "./http/httpApi";

/**
 * The API the app talks to, chosen at build time:
 * - `VITE_API=http`: the session API of services/api, through the dev proxy or `VITE_API_URL`;
 * - anything else: the in-browser mock.
 *
 * The mock is imported only when it is used, so a build for the real API carries neither the mock tutor
 * nor the answers of the practice items.
 */
export async function createApi(): Promise<SessionApi> {
  if (import.meta.env.VITE_API === "http") {
    return createHttpApi({ baseUrl: import.meta.env.VITE_API_URL ?? "" });
  }
  const { createMockApi } = await import("./mock/mockApi");
  return createMockApi();
}
