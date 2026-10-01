import { afterEach, describe, expect, it, vi } from "vitest";

import { createApi } from "./index";

describe("createApi", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("uses the in-browser mock unless told otherwise", async () => {
    expect((await createApi()).engine).toBe("mock");
  });

  it("uses the HTTP session API with VITE_API=http", async () => {
    vi.stubEnv("VITE_API", "http");
    const api = await createApi();
    expect(api.engine).toBe("live");
    expect(api.resetDemoData).toBeUndefined();
  });
});
