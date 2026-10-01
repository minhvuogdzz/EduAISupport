import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { ApiProvider } from "./api/ApiProvider";
import type { SessionApi } from "./api/client";

export function AppProviders({
  api,
  queryClient,
  children,
}: {
  api: SessionApi;
  queryClient: QueryClient;
  children: ReactNode;
}) {
  return (
    <ApiProvider api={api}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ApiProvider>
  );
}
