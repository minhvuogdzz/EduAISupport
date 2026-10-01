import type { ReactNode } from "react";

import { ApiContext } from "./apiContext";
import type { SessionApi } from "./client";

export function ApiProvider({ api, children }: { api: SessionApi; children: ReactNode }) {
  return <ApiContext value={api}>{children}</ApiContext>;
}
