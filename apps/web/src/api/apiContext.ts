import { createContext, useContext } from "react";

import type { SessionApi } from "./client";

export const ApiContext = createContext<SessionApi | null>(null);

export function useApi(): SessionApi {
  const api = useContext(ApiContext);
  if (!api) throw new Error("useApi() must be used inside <ApiProvider>");
  return api;
}
