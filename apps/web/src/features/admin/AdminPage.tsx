import { useState, type FormEvent } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "../../components/AppShell";
import { adminLogin, adminOverview, AdminError, type OperationLog } from "./adminApi";
import "./admin.css";

const TOKEN_KEY = "monkey.admin.session";
const KIND = {
  model: "Model của Gia sư Buddy",
  rag: "RAG",
  web: "Tra cứu web",
  network: "Kết nối HTTP",
  cache: "Bộ nhớ đệm",
  decision: "Định tuyến nguồn",
  command: "Lượt xử lý",
};
const STATUS: Record<string, string> = {
  running: "Đang chạy",
  success: "Thành công",
  miss: "Không có nguồn phù hợp",
  error: "Lỗi",
  fallback: "Dự phòng",
  skipped: "Không gửi",
  interrupted: "Gián đoạn",
};
const REASON: Record<string, string> = {
  web_disabled: "Chưa bật nguồn web",
  question_outside_web_scope: "Câu hỏi ngoài phạm vi tra cứu",
  no_scoped_web_topic: "Chưa xác định chủ đề để tìm",
  web_no_accepted_source: "Không có nguồn web qua kiểm tra",
  web_page_cache_hit: "Đọc trang từ bộ nhớ đệm",
  official_page_cache_hit: "Đọc nguồn chính thức từ bộ nhớ đệm",
  wikipedia_cache_hit: "Đọc kết quả Wikipedia từ bộ nhớ đệm",
};
const number = (value: number) => value.toLocaleString("vi-VN");
const time = (value: string | null) =>
  value ? new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour12: false }) : "—";
function savedToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}
function saveToken(token: string) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* Memory-only login remains available. */
  }
}
function origin(row: OperationLog) {
  return (
    row.model ||
    row.details.search_engine ||
    row.details.title ||
    row.details.semantic ||
    REASON[row.purpose] ||
    row.purpose ||
    row.operation
  );
}

export function AdminPage() {
  const [token, setToken] = useState(savedToken);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState(true);
  const [view, setView] = useState<"activity" | "sources" | "models">("activity");
  const [scope, setScope] = useState<"runtime" | "history">("history");
  const [kind, setKind] = useState("");
  const [search, setSearch] = useState("");
  const [session, setSession] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<OperationLog | null>(null);
  const queryClient = useQueryClient();
  const data = useQuery({
    queryKey: ["admin-overview", token, session, kind, search, page],
    queryFn: () => adminOverview(token, session, kind, search, page * 12),
    placeholderData: keepPreviousData,
    enabled: !!token,
    retry: false,
    refetchInterval: live ? 5000 : false,
  });
  const expired = data.error instanceof AdminError && data.error.status === 401;
  async function login(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await adminLogin(password);
      saveToken(result.token);
      setToken(result.token);
      setPassword("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Chưa đăng nhập được.");
    } finally {
      setBusy(false);
    }
  }
  function logout() {
    saveToken("");
    setToken("");
    queryClient.removeQueries({ queryKey: ["admin-overview"] });
  }
  function filter(value: string) {
    setKind(value);
    setPage(0);
    setSelected(null);
  }
  function changeScope(value: "history" | "runtime") {
    setScope(value);
    setPage(0);
    setSelected(null);
  }
  const overview = data.data;
  const source = overview?.[scope];
  const totals = source?.totals;
  const rows = source?.logs ?? [];
  const activeRow = rows.find((r) => r.id === selected?.id) ?? selected;
  const models = new Map<string, NonNullable<typeof overview>["models"]>();
  overview?.models.forEach((model) => models.set(model.model, [...(models.get(model.model) ?? []), model]));
  return (
    <AppShell>
      <title>Admin · Phòng quan sát Gia sư Buddy · Monkey Edu</title>
      <div className="admin-page">
        <header className="admin-heading">
          <div>
            <p className="eyebrow">MONKEY EDU / ADMIN</p>
            <h1>
              Phòng quan sát Gia sư Buddy<span>.</span>
            </h1>
            <p>Hiểu từng lượt xử lý. Kiểm chứng từng nguồn trả lời.</p>
          </div>
          <span className="admin-readonly">Chỉ đọc · Dữ liệu thực tế</span>
        </header>
        {!token || expired ? (
          <section className="admin-login">
            <span className="admin-login-mark" aria-hidden="true">
              ⌘
            </span>
            <h2>Đăng nhập quản trị</h2>
            <p>Theo dõi hoạt động Gia sư Buddy và các nguồn kiến thức.</p>
            <form onSubmit={(event) => void login(event)}>
              <label htmlFor="admin-password">Mật khẩu Admin</label>
              <input
                id="admin-password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoFocus
              />
              <button className="ink-button" disabled={busy}>
                {busy ? "Đang kiểm tra…" : "Vào trang Admin ↗"}
              </button>
            </form>
            {(error || expired) && (
              <p role="alert">{error || "Phiên Admin đã hết hạn. Anh đăng nhập lại nhé."}</p>
            )}
          </section>
        ) : (
          <>
            <div className="admin-toolbar">
              <div className="admin-live">
                <i className={live ? "is-live" : ""} />
                {live ? "Trực tiếp · 5 giây" : "Đã tạm dừng"}
                <small>{overview ? time(overview.generated_at) : "Đang kết nối…"}</small>
              </div>
              <div>
                <button onClick={() => setLive(!live)}>{live ? "Tạm dừng" : "Tiếp tục"}</button>
                <button onClick={() => void data.refetch()} disabled={data.isFetching}>
                  Làm mới
                </button>
                <button onClick={logout}>Đăng xuất</button>
              </div>
            </div>
            {data.isError && (
              <p role="alert" className="admin-error">
                {data.error.message}
              </p>
            )}
            {data.isPending && <p role="status">Đang đọc nhật ký vận hành…</p>}
            {overview && source && totals && (
              <>
                <div className="admin-navigation">
                  <nav className="admin-tabs" aria-label="Góc nhìn nhật ký">
                    {(
                      [
                        ["activity", "Nhật ký hoạt động"],
                        ["sources", "RAG & Internet"],
                        ["models", "Model & usage"],
                      ] as const
                    ).map(([id, label]) => (
                      <button key={id} aria-pressed={view === id} onClick={() => setView(id)}>
                        {label}
                      </button>
                    ))}
                  </nav>
                  <label className="admin-scope">
                    Phạm vi dữ liệu
                    <select
                      value={scope}
                      onChange={(e) => changeScope(e.target.value as "history" | "runtime")}
                    >
                      <option value="history">Lịch sử buổi học</option>
                      <option value="runtime">Vận hành gần đây</option>
                    </select>
                  </label>
                </div>
                <div className="admin-coverage">
                  <span>
                    <strong>
                      {scope === "history"
                        ? `${overview.history.sessions.length} buổi học gần nhất`
                        : `${number(overview.runtime.retained)} tác vụ được giữ`}
                    </strong>{" "}
                    ·{" "}
                    {scope === "history"
                      ? "Lịch sử lưu model, RAG và nguồn web; chưa lưu kết nối HTTP hay cache."
                      : `Tối đa ${number(overview.runtime.capacity)} tác vụ. HTTP và cache được ghi từ bản cập nhật này.`}
                  </span>
                  {scope === "history" && (
                    <button
                      onClick={() => {
                        changeScope("runtime");
                        setView("sources");
                        filter("");
                      }}
                    >
                      Xem HTTP thực tế ↗
                    </button>
                  )}
                </div>
                <div className="admin-metrics">
                  <Metric
                    label="Lượt gửi model"
                    value={number(totals.calls_sent)}
                    note={`${number(totals.model_operations)} tác vụ Gia sư Buddy`}
                    onClick={() => {
                      filter("model");
                      setView("activity");
                    }}
                  />
                  <Metric
                    label="Truy xuất RAG"
                    value={number(totals.rag)}
                    note={`${number(totals.rag_hits)} có căn cứ`}
                    onClick={() => {
                      filter("rag");
                      setView("activity");
                    }}
                  />
                  <Metric
                    label={scope === "history" ? "Nguồn web đã lưu" : "Tra cứu web"}
                    value={number(totals.web)}
                    note={
                      scope === "history"
                        ? "Không gồm các lần tìm thất bại"
                        : `${number(totals.web_hits)} có kết quả`
                    }
                    onClick={() => {
                      filter("web");
                      setView("activity");
                    }}
                  />
                  <Metric
                    label="Kết nối internet"
                    value={source.coverage.network_tracked ? number(totals.network) : "—"}
                    note={
                      source.coverage.network_tracked
                        ? `${number(totals.network_errors)} lỗi HTTP / mạng`
                        : "Lịch sử chưa theo dõi HTTP"
                    }
                    onClick={() => {
                      changeScope("runtime");
                      filter("network");
                      setView("activity");
                    }}
                  />
                  <Metric
                    label="Token vào / ra"
                    value={`${number(totals.prompt_tokens)} / ${number(totals.completion_tokens)}`}
                    note={`${number(totals.unknown_usage)} tác vụ chưa báo token`}
                  />
                </div>
                {overview.runtime.persistence_error && scope === "runtime" && (
                  <p role="status" className="admin-error">
                    Chưa ghi được tệp nhật ký; tác vụ mới đang được giữ trong bộ nhớ máy chủ.
                  </p>
                )}
                {view === "sources" && (
                  <section className="admin-source-section">
                    <div className="admin-section-title">
                      <div>
                        <h2>Hệ thống đã tìm kiến thức ở đâu?</h2>
                        <p>
                          RAG → tra cứu web khi cần → kết nối HTTP hoặc bộ nhớ đệm. Mỗi bước được đếm riêng.
                          HTTP ở đây chỉ tính kết nối tìm nguồn web.
                        </p>
                      </div>
                      <span className="admin-chip">Chế độ web: {overview.web_mode}</span>
                    </div>
                    <div className="admin-source-grid">
                      <SourceCard
                        step="01"
                        title="Kho kiến thức · RAG"
                        value={totals.rag}
                        hit={totals.rag_hits}
                        outcome="có căn cứ"
                        note="Truy xuất tài liệu bài học; có căn cứ khi tìm được đoạn phù hợp."
                        onClick={() => {
                          filter("rag");
                          setView("activity");
                        }}
                      />
                      <SourceCard
                        step="02"
                        title={scope === "history" ? "Nguồn web đã lưu" : "Tra cứu nguồn web"}
                        value={totals.web}
                        hit={totals.web_hits}
                        outcome={scope === "history" ? "đã dùng để trả lời" : "có kết quả"}
                        note={
                          scope === "history"
                            ? "Sự kiện cũ chỉ lưu nguồn đã tìm được, không đủ để đếm mọi lần thử tra cứu."
                            : "Lượt gọi bộ tra cứu, có thể dùng cache hoặc gọi tiếp bộ tra cứu dự phòng."
                        }
                        onClick={() => {
                          filter("web");
                          setView("activity");
                        }}
                      />
                      <article className="admin-source-card">
                        <span className="admin-source-step">03</span>
                        <h3>Kết nối ra internet</h3>
                        <strong>
                          {source.coverage.network_tracked ? number(totals.network) : "Chưa theo dõi"}
                        </strong>
                        <p>
                          {source.coverage.network_tracked
                            ? `${totals.network_errors} kết nối lỗi · ${totals.cache} lần đọc cache`
                            : "Lịch sử cũ không lưu số yêu cầu HTTP. Chuyển sang vận hành để kiểm tra."}
                        </p>
                        <p>Một lượt tra cứu có thể gửi nhiều HTTP, hoặc không gửi nếu có cache.</p>
                        <button
                          onClick={() => {
                            changeScope("runtime");
                            filter("network");
                            setView("activity");
                          }}
                        >
                          Xem từng kết nối ↗
                        </button>
                      </article>
                    </div>
                    <div className="admin-source-explainer">
                      <h3>Vì sao chưa thấy truy cập internet?</h3>
                      <p>
                        Nếu RAG đã đủ căn cứ, hệ thống có thể trả lời mà không tìm web. Nguồn web cũng có thể
                        được đọc từ cache. Số 0 trong vận hành chỉ là chưa ghi nhận kết nối trong phạm vi đang
                        giữ.
                      </p>
                      <div className="admin-decision-list">
                        {Object.entries(totals.decisions).map(([reason, count]) => (
                          <button
                            key={reason}
                            onClick={() => {
                              filter("decision");
                              setSearch(reason);
                              setView("activity");
                            }}
                          >
                            {REASON[reason] ?? reason}
                            <b>{number(count)}</b>
                          </button>
                        ))}
                        {!Object.keys(totals.decisions).length && (
                          <span>
                            Chưa có dấu vết định tuyến trong phạm vi này. Các lượt mới sẽ ghi lý do khi bỏ qua
                            hoặc không tìm được nguồn web.
                          </span>
                        )}
                      </div>
                      <button
                        className="admin-inline-link"
                        onClick={() => {
                          changeScope("runtime");
                          filter("cache");
                          setView("activity");
                        }}
                      >
                        Kiểm tra các lần dùng bộ nhớ đệm →
                      </button>
                    </div>
                  </section>
                )}
                {view === "models" && (
                  <section className="admin-panel">
                    <div className="admin-section-title">
                      <div>
                        <h2>Model & mức sử dụng</h2>
                        <p>
                          Gộp theo model. Ưu tiên được ghi riêng cho từng vai trò; trạng thái quota là quan
                          sát của máy chủ.
                        </p>
                      </div>
                    </div>
                    <div className="admin-table-scroll">
                      <table className="admin-table">
                        <thead>
                          <tr>
                            <th>Model</th>
                            <th>Vai trò · thứ tự ưu tiên</th>
                            <th>Gửi / có trả lời</th>
                            <th>Token vào / ra</th>
                            <th>Provider / quota</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[...new Set([...models.keys(), ...Object.keys(totals.usage_by_model)])].map(
                            (name) => {
                              const configured = models.get(name) ?? [];
                              const model = configured[0];
                              const usage = totals.usage_by_model[name];
                              return (
                                <tr key={name}>
                                  <td>
                                    <code>{name}</code>
                                  </td>
                                  <td>
                                    <div className="admin-role-chips">
                                      {configured.map((m) => (
                                        <span key={m.model_class}>
                                          {m.model_class} #{m.priority}
                                        </span>
                                      ))}
                                    </div>
                                  </td>
                                  <td>{usage ? `${usage.sent} / ${usage.answered}` : "Chưa ghi nhận"}</td>
                                  <td>
                                    {usage
                                      ? `${number(usage.prompt_tokens)} / ${number(usage.completion_tokens)}`
                                      : "—"}
                                  </td>
                                  <td>
                                    {!model
                                      ? "Ngoài chuỗi hiện tại"
                                      : !model.provider_configured
                                        ? "Chưa cấu hình"
                                        : model.quota_exhausted
                                          ? "Tạm nghỉ · hết quota"
                                          : "Đã cấu hình · chưa chặn quota"}
                                    {model?.reset_at && <small>Thử lại: {time(model.reset_at)}</small>}
                                  </td>
                                </tr>
                              );
                            },
                          )}
                        </tbody>
                      </table>
                    </div>
                    <p className="admin-note">
                      Chỉ cộng token provider báo về. Hạn mức thực tế của tài khoản provider không được suy ra
                      từ số lần gọi.
                    </p>
                  </section>
                )}
                {view === "activity" && (
                  <section className="admin-panel">
                    <div className="admin-section-title">
                      <div>
                        <h2>Nhật ký hoạt động</h2>
                        <p>Chọn một dòng để xem nguồn, lần thử model và dấu vết của lượt xử lý.</p>
                      </div>
                      <span className="admin-chip">{number(source.filtered_total)} bản ghi phù hợp</span>
                    </div>
                    <div className="admin-filters">
                      <label>
                        Loại tác vụ
                        <select value={kind} onChange={(e) => filter(e.target.value)}>
                          <option value="">Tất cả tác vụ</option>
                          {Object.entries(KIND).map(([id, label]) => (
                            <option key={id} value={id}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Tìm trong nhật ký
                        <input
                          value={search}
                          maxLength={200}
                          onChange={(e) => {
                            setSearch(e.target.value);
                            setPage(0);
                            setSelected(null);
                          }}
                          placeholder="Model, mục đích, request…"
                        />
                      </label>
                      <label>
                        Lọc theo mã buổi
                        <input
                          value={session}
                          maxLength={120}
                          onChange={(e) => {
                            setSession(e.target.value);
                            setPage(0);
                            setSelected(null);
                          }}
                          placeholder="Tất cả buổi học"
                        />
                      </label>
                    </div>
                    {data.isPlaceholderData && (
                      <p role="status" className="admin-note">
                        Đang lọc nhật ký…
                      </p>
                    )}
                    <div className={`admin-log-layout ${activeRow ? "has-detail" : ""}`}>
                      <div className="admin-table-scroll">
                        <table className="admin-table">
                          <thead>
                            <tr>
                              <th>Thời gian</th>
                              <th>Tác vụ / nguồn</th>
                              <th>Token vào / ra</th>
                              <th>Độ trễ</th>
                              <th>Kết quả</th>
                              <th>
                                <span className="sr-only">Chi tiết</span>
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {rows.map((row) => (
                              <tr key={row.id} className={activeRow?.id === row.id ? "is-selected" : ""}>
                                <td>
                                  <time dateTime={row.started_at}>{time(row.started_at)}</time>
                                  <small title={row.session_id ?? ""}>
                                    {row.session_id ? `Buổi ${row.session_id.slice(-8)}` : "Ngoài buổi học"}
                                  </small>
                                </td>
                                <td>
                                  <span className={`admin-kind kind-${row.kind}`}>{KIND[row.kind]}</span>
                                  <code className="admin-origin" title={origin(row)}>
                                    {origin(row)}
                                  </code>
                                </td>
                                <td className="admin-tokens">
                                  {row.prompt_tokens === null ? "—" : number(row.prompt_tokens)} /{" "}
                                  {row.completion_tokens === null ? "—" : number(row.completion_tokens)}
                                </td>
                                <td>{row.duration_ms === null ? "—" : `${number(row.duration_ms)} ms`}</td>
                                <td>
                                  <span className={`admin-status status-${row.status}`}>
                                    {STATUS[row.status] ?? row.status}
                                  </span>
                                </td>
                                <td>
                                  <button
                                    aria-label={`Xem dấu vết ${row.id}`}
                                    aria-expanded={activeRow?.id === row.id}
                                    onClick={() => setSelected(activeRow?.id === row.id ? null : row)}
                                  >
                                    Chi tiết ↗
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {!rows.length && (
                          <div className="admin-empty">
                            <h3>Chưa có tác vụ trong phạm vi này</h3>
                            <p>
                              {scope === "history" &&
                              ["network", "cache", "decision", "command"].includes(kind)
                                ? "Loại dấu vết này chỉ có trong nhật ký vận hành gần đây."
                                : "Thử đổi phạm vi hoặc bỏ bộ lọc. Nhật ký sẽ xuất hiện khi hệ thống thực sự hoạt động."}
                            </p>
                          </div>
                        )}
                      </div>
                      {activeRow && (
                        <TraceDetail
                          row={activeRow}
                          onClose={() => setSelected(null)}
                          onRequest={() => {
                            changeScope("runtime");
                            filter("");
                            setSearch(activeRow.request_id ?? "");
                          }}
                        />
                      )}
                    </div>
                    <div className="admin-pagination">
                      <span>
                        {source.filtered_total
                          ? `${page * 12 + 1}–${Math.min(page * 12 + 12, source.filtered_total)}`
                          : "0"}{" "}
                        / {number(source.filtered_total)} bản ghi
                      </span>
                      <div>
                        <button
                          disabled={page === 0 || data.isPlaceholderData}
                          onClick={() => {
                            setPage(page - 1);
                            setSelected(null);
                          }}
                        >
                          ← Trước
                        </button>
                        <span>Trang {page + 1}</span>
                        <button
                          disabled={(page + 1) * 12 >= source.filtered_total || data.isPlaceholderData}
                          onClick={() => {
                            setPage(page + 1);
                            setSelected(null);
                          }}
                        >
                          Sau →
                        </button>
                      </div>
                    </div>
                  </section>
                )}
                <p className="admin-footnote">
                  Hai phạm vi có thể chứa cùng một tác vụ, không cộng chồng. “—” là chưa có số liệu. Không lưu
                  nội dung học sinh, prompt hay khóa API.
                </p>
              </>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
function Metric({
  label,
  value,
  note,
  onClick,
}: {
  label: string;
  value: string;
  note: string;
  onClick?: () => void;
}) {
  return (
    <article className="admin-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
      {onClick && (
        <button onClick={onClick} aria-label={`Xem ${label}`}>
          ↗
        </button>
      )}
    </article>
  );
}
function SourceCard({
  step,
  title,
  value,
  hit,
  outcome,
  note,
  onClick,
}: {
  step: string;
  title: string;
  value: number;
  hit: number;
  outcome: string;
  note: string;
  onClick: () => void;
}) {
  return (
    <article className="admin-source-card">
      <span className="admin-source-step">{step}</span>
      <h3>{title}</h3>
      <strong>
        {number(value)} <small>lượt</small>
      </strong>
      <div className="admin-source-bar">
        <span style={{ width: `${value ? (hit / value) * 100 : 0}%` }} />
      </div>
      <p>
        {number(hit)} / {number(value)} lượt {outcome}
      </p>
      <p>{note}</p>
      <button onClick={onClick}>Xem dấu vết ↗</button>
    </article>
  );
}
function TraceDetail({
  row,
  onClose,
  onRequest,
}: {
  row: OperationLog;
  onClose: () => void;
  onRequest: () => void;
}) {
  const d = row.details;
  const url = d.url && /^https?:\/\//.test(d.url) ? d.url : null;
  return (
    <aside className="admin-trace" aria-label="Chi tiết dấu vết">
      <div className="admin-trace-heading">
        <h3>{KIND[row.kind]}</h3>
        <button onClick={onClose} aria-label="Đóng chi tiết">
          ×
        </button>
      </div>
      <span className={`admin-status status-${row.status}`}>{STATUS[row.status] ?? row.status}</span>
      <dl>
        <dt>Mục đích</dt>
        <dd>{REASON[row.purpose] ?? row.purpose}</dd>
        <dt>Tác vụ</dt>
        <dd>{row.operation}</dd>
        <dt>Thời điểm</dt>
        <dd>{time(row.started_at)}</dd>
        {row.model_class && (
          <>
            <dt>Vai trò model</dt>
            <dd>{row.model_class}</dd>
          </>
        )}
        {row.session_id && (
          <>
            <dt>Buổi học</dt>
            <dd>
              <code>{row.session_id}</code>
            </dd>
          </>
        )}
        {row.request_id && (
          <>
            <dt>Request</dt>
            <dd>
              <code>{row.request_id}</code>
            </dd>
          </>
        )}
        {row.parent_id && (
          <>
            <dt>Tác vụ cha</dt>
            <dd>
              <code>{row.parent_id}</code>
            </dd>
          </>
        )}
        {row.path && (
          <>
            <dt>API</dt>
            <dd>{row.path}</dd>
          </>
        )}
        {d.http_status !== undefined && (
          <>
            <dt>HTTP</dt>
            <dd>
              {d.method ?? ""} {d.http_status}
            </dd>
          </>
        )}
        {d.grounding && (
          <>
            <dt>Đối chiếu nguồn</dt>
            <dd>{d.grounding}</dd>
          </>
        )}
        {d.node_id && (
          <>
            <dt>Bài học</dt>
            <dd>{d.node_id}</dd>
          </>
        )}
        {d.fallback_reason && (
          <>
            <dt>Lý do dự phòng</dt>
            <dd>{d.fallback_reason}</dd>
          </>
        )}
        {d.error && (
          <>
            <dt>Lỗi</dt>
            <dd>{d.error}</dd>
          </>
        )}
      </dl>
      {d.model_calls !== undefined && (
        <p className="admin-trace-summary">
          {d.model_calls} lần gửi model · {d.rag_calls} RAG · {d.web_calls} tra cứu web ·{" "}
          {d.network_calls ?? "—"} HTTP · {d.cache_calls ?? "—"} cache
          {d.model_calls === 0 && " · Không gọi model"}
        </p>
      )}
      {!!d.attempts?.length && (
        <div>
          <h4>Các lần thử model</h4>
          {d.attempts.map((a, i) => (
            <p className="admin-attempt" key={i}>
              <code>{a.model}</code>
              <span>
                {a.sent ? "Đã gửi" : "Bỏ qua"} · {a.error ?? (a.sent ? "Có trả lời" : "Chưa gửi provider")}
                {a.limit ? ` · ${a.limit}` : ""}
                {a.retry_after_s != null ? ` · thử lại sau ${a.retry_after_s}s` : ""}
              </span>
            </p>
          ))}
        </div>
      )}
      {!!d.chunks?.length && (
        <div>
          <h4>Đoạn kiến thức truy xuất</h4>
          {d.chunks.map((c) => (
            <p className="admin-attempt" key={c.id}>
              <strong>{c.title}</strong>
              <code>{c.id}</code>
            </p>
          ))}
        </div>
      )}
      {d.answered !== undefined && (
        <p>{d.answered ? "Nguồn đã được dùng để trả lời." : "Nguồn chưa được dùng để trả lời."}</p>
      )}
      {url && (
        <a className="admin-source-link" href={url} target="_blank" rel="noreferrer">
          {d.title || url} ↗
        </a>
      )}
      {row.request_id && (
        <button className="admin-request-button" onClick={onRequest}>
          Xem toàn bộ tác vụ cùng request →
        </button>
      )}
    </aside>
  );
}
