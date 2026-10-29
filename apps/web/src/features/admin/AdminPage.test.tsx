import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderApp } from "../../test/renderApp";

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});
describe("Admin's independent server login", () => {
  it("does not reveal operational logs until the server accepts the password", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "Mật khẩu Admin chưa đúng." } }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetcher);
    const { user } = renderApp("/admin");
    expect(await screen.findByRole("heading", { name: "Đăng nhập quản trị" })).toBeVisible();
    expect(fetcher).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Mật khẩu Admin"), "9999");
    await user.click(screen.getByRole("button", { name: /Vào trang Admin/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Mật khẩu Admin chưa đúng.");
    expect(sessionStorage.getItem("monkey.admin.session")).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Góc nhìn nhật ký" })).not.toBeInTheDocument();
    expect(fetcher.mock.calls[0][0]).toMatch(/\/v1\/admin\/login$/);
  });
  it("asks for the Admin password again when a saved token has expired", async () => {
    sessionStorage.setItem("monkey.admin.session", "expired-token");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { message: "Vui lòng đăng nhập Admin." } }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    renderApp("/admin");
    expect(await screen.findByRole("heading", { name: "Đăng nhập quản trị" })).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("Phiên Admin đã hết hạn");
  });
});

it("pages logs and distinguishes untracked historical HTTP from an observed zero", async () => {
  const { within } = await import("@testing-library/react");
  const totals = {
    usage_by_model: {},
    operations: 13,
    model_operations: 0,
    calls_sent: 0,
    prompt_tokens: 0,
    completion_tokens: 0,
    unknown_usage: 0,
    rag: 13,
    rag_hits: 13,
    web: 0,
    web_hits: 0,
    network: 0,
    network_errors: 0,
    cache: 0,
    decisions: {},
    commands: 0,
    errors: 0,
    by_model: {},
  };
  const rows = Array.from({ length: 13 }, (_, i) => ({
    id: `row-${i}`,
    kind: "rag",
    operation: "retrieve",
    status: "success",
    started_at: "2026-10-29T06:00:00Z",
    session_id: "session-1",
    request_id: null,
    parent_id: null,
    path: null,
    duration_ms: 12,
    model: null,
    model_class: null,
    purpose: `source-${i}`,
    prompt_tokens: null,
    completion_tokens: null,
    calls_sent: 0,
    details: {},
  }));
  sessionStorage.setItem("monkey.admin.session", "accepted-token");
  const fetcher = vi.fn((url: string) => {
    const params = new URL(url, "http://localhost").searchParams;
    const offset = Number(params.get("offset"));
    const common = { totals, logs: rows.slice(offset, offset + 12), filtered_total: 13 };
    return Promise.resolve(
      new Response(
        JSON.stringify({
          generated_at: "2026-10-29T06:00:00Z",
          runtime: {
            ...common,
            coverage: { network_tracked: true, from: null },
            retained: 13,
            capacity: 3000,
            persistence_error: false,
          },
          history: {
            ...common,
            coverage: { network_tracked: false, from: null },
            sessions: [],
            session_limit: 50,
          },
          models: [],
          web_mode: "search",
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );
  });
  vi.stubGlobal("fetch", fetcher);
  const { user } = renderApp("/admin");
  expect(await screen.findByText("Lịch sử chưa theo dõi HTTP")).toBeVisible();
  expect(screen.getByRole("button", { name: "Xem dấu vết row-0" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Xem dấu vết row-12" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Sau →" }));
  expect(await screen.findByRole("button", { name: "Xem dấu vết row-12" })).toBeVisible();
  expect(fetcher.mock.calls.some(([url]) => url.includes("offset=12"))).toBe(true);
  await user.click(screen.getByRole("button", { name: "Xem dấu vết row-12" }));
  expect(
    within(screen.getByRole("complementary", { name: "Chi tiết dấu vết" })).getByText("source-12"),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Xem HTTP thực tế ↗" }));
  expect(await screen.findByText("0 lỗi HTTP / mạng")).toBeVisible();
  expect(screen.queryByText("Lịch sử chưa theo dõi HTTP")).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Hệ thống đã tìm kiến thức ở đâu?" })).toBeVisible();
});
