import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

import type { SessionApi } from "../api/client";
import { createMockApi, type MockApiOptions } from "../api/mock/mockApi";
import { App } from "../App";
import { AppProviders } from "../AppProviders";

/** The mock API without delays, memory-only, no demo data unless asked. */
export function testApi(options: MockApiOptions = {}): SessionApi {
  return createMockApi({ latencyMs: 0, typingDelayMs: 0, seed: false, storage: null, ...options });
}

/** Renders the whole app at `route`, as main.tsx does, with a MemoryRouter. */
export function renderApp(route: string, api: SessionApi = testApi()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  const view = render(
    <AppProviders api={api} queryClient={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </AppProviders>,
  );
  return { ...view, user, api, queryClient };
}
