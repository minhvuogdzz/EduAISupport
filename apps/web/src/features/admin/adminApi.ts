export type LogKind = "model" | "rag" | "web" | "command" | "network" | "cache" | "decision";
export interface OperationLog {
  id: string;
  kind: LogKind;
  operation: string;
  status: string;
  started_at: string;
  session_id: string | null;
  request_id: string | null;
  parent_id: string | null;
  path: string | null;
  duration_ms: number | null;
  model: string | null;
  model_class: string | null;
  purpose: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  calls_sent: number;
  details: {
    attempts?: {
      model: string;
      sent: boolean;
      error: string | null;
      limit: string | null;
      retry_after_s: number | null;
    }[];
    fallback_reason?: string;
    error?: string;
    grounded?: boolean;
    grounding?: string;
    semantic?: string;
    node_id?: string;
    chunks?: { id: string; title: string }[];
    title?: string;
    url?: string;
    retrieval?: string;
    search_engine?: string;
    answered?: boolean;
    http_status?: number;
    method?: string;
    model_calls?: number;
    rag_calls?: number;
    web_calls?: number;
    network_calls?: number;
    cache_calls?: number;
  };
}
interface Totals {
  usage_by_model: Record<
    string,
    { sent: number; answered: number; prompt_tokens: number; completion_tokens: number }
  >;
  network: number;
  network_errors: number;
  cache: number;
  rag_hits: number;
  web_hits: number;
  commands: number;
  decisions: Record<string, number>;
  operations: number;
  model_operations: number;
  calls_sent: number;
  prompt_tokens: number;
  completion_tokens: number;
  unknown_usage: number;
  rag: number;
  web: number;
  errors: number;
  by_model: Record<string, number>;
}
export interface AdminOverview {
  generated_at: string;
  runtime: {
    totals: Totals;
    logs: OperationLog[];
    filtered_total: number;
    coverage: { network_tracked: boolean; from: string | null };
    retained: number;
    capacity: number;
    persistence_error: boolean;
  };
  history: {
    totals: Totals;
    logs: OperationLog[];
    filtered_total: number;
    coverage: { network_tracked: boolean; from: string | null };
    sessions: { id: string; chapter: string; updated_at: string }[];
    session_limit: number;
  };
  models: {
    model_class: string;
    model: string;
    priority: number;
    quota_exhausted: boolean;
    reset_at: string | null;
    provider_configured: boolean;
  }[];
  web_mode: string;
}
export class AdminError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
const base = import.meta.env.VITE_API_URL ?? "";
async function request<T>(path: string, options: RequestInit): Promise<T> {
  const response = await fetch(`${base}/v1/admin${path}`, { ...options, cache: "no-store" });
  if (!response.ok) {
    let message = `Không tải được dữ liệu Admin (${response.status}).`;
    try {
      const body = (await response.json()) as { error?: { message?: string } };
      message = body.error?.message ?? message;
    } catch {
      /* Keep the HTTP error when a proxy returns HTML. */
    }
    throw new AdminError(message, response.status);
  }
  return response.json() as Promise<T>;
}
export function adminLogin(password: string) {
  return request<{ token: string; expires_in: number }>("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
}
export function adminOverview(token: string, sessionId = "", kind = "", search = "", offset = 0) {
  const params = new URLSearchParams({ limit: "12", offset: String(offset) });
  if (sessionId) params.set("session_id", sessionId);
  if (kind) params.set("kind", kind);
  if (search) params.set("search", search);
  return request<AdminOverview>(`/overview?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}
