import { afterEach, describe, expect, it, vi } from "vitest";

import { newId } from "./ids";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("newId", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns a v4 uuid", () => {
    expect(newId()).toMatch(UUID_V4);
  });

  it("works where crypto.randomUUID is missing (plain-HTTP LAN access)", () => {
    const real = globalThis.crypto;
    const getRandomValues = vi.fn((array: Uint8Array<ArrayBuffer>) => real.getRandomValues(array));
    vi.stubGlobal("crypto", { getRandomValues });
    const ids = new Set(Array.from({ length: 50 }, newId));
    expect(getRandomValues).toHaveBeenCalledTimes(50);
    expect(ids.size).toBe(50);
    for (const id of ids) expect(id).toMatch(UUID_V4);
  });
});
