import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { useApi } from "../../api/apiContext";
import type { RagMode, RagResult, RagSearch, RagStatus } from "../../api/contract";
import { AppShell } from "../../components/AppShell";
import { MathText } from "../../components/MathText";
import { formatViDateTime, formatViDecimal } from "../../lib/viNumber";
import { TeacherHeader } from "./TeacherHeader";

const KIND_LABEL: Record<string, string> = {
  theory: "Lý thuyết",
  method: "Phương pháp",
  worked_example: "Cô làm mẫu",
  misconception_note: "Lỗi sai hay gặp",
  source_passage: "Đoạn tài liệu",
};

const SOURCE_LABEL: Record<string, string> = {
  chapter: "Nội dung chương",
  document: "Tài liệu giáo viên",
};

const MODE_LABEL: Record<RagSearch["mode"], string> = {
  question: "Học sinh hỏi",
  definition: "Học sinh hỏi định nghĩa",
  teach: "Giảng bài",
  hint: "Gợi ý",
};

const PREVIEW_CHARS = 220;

function decimal(value: number, digits: number): string {
  return formatViDecimal(value.toFixed(digits));
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="card p-5">
      {children}
    </p>
  );
}

function semanticLine(status: RagStatus): string {
  if (status.semantic === "off") {
    return status.semantic_error
      ? `Ngữ nghĩa: tạm tắt vì lỗi gọi model (${status.semantic_error}); đang dùng từ khóa và cấu trúc.`
      : "Ngữ nghĩa: tắt (chưa có khóa Gemini); đang dùng từ khóa và cấu trúc đồ thị.";
  }
  return status.semantic_is_model
    ? `Ngữ nghĩa: vector ${status.semantic}, cùng từ khóa và cấu trúc đồ thị.`
    : `Ngữ nghĩa: vector thử nghiệm ${status.semantic} (chỉ so chữ, không hiểu nghĩa).`;
}

/** Where the tutor's content comes from (RAG-1): every source, and what one question retrieves. */
export function RagPage() {
  const api = useApi();
  const status = useQuery({
    queryKey: ["rag-status"],
    queryFn: () => api.rag!.status(),
    enabled: api.rag !== undefined,
    retry: false,
  });
  let body: ReactNode;
  if (!api.rag) body = <Notice>Tra cứu RAG cần máy chủ thật: chạy bản demo bằng lệnh make demo.</Notice>;
  else if (status.isPending) body = <Notice>Đang dựng chỉ mục…</Notice>;
  else if (status.isError) body = <Notice>Chưa đọc được chỉ mục RAG.</Notice>;
  else
    body = (
      <>
        <Sources status={status.data} />
        <Search status={status.data} />
      </>
    );
  return (
    <AppShell>
      <title>RAG · Giáo viên · CAVAT</title>
      <TeacherHeader title="Gia sư lấy nội dung ở đâu" />
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 pb-10">{body}</div>
    </AppShell>
  );
}

function Sources({ status }: { status: RagStatus }) {
  const api = useApi();
  const queryClient = useQueryClient();
  const rebuild = useMutation({
    mutationFn: () => api.rag!.rebuild(),
    onSuccess: (data) => queryClient.setQueryData(["rag-status"], data),
  });
  return (
    <section aria-labelledby="rag-sources" className="card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="rag-sources" className="font-bold">
            Kho đoạn: {status.chunks} đoạn
          </h2>
          <p className="text-sm text-slate-600">{semanticLine(status)}</p>
          {status.built_at && (
            <p className="text-xs text-slate-500">Dựng lúc {formatViDateTime(status.built_at)}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => rebuild.mutate()}
          disabled={rebuild.isPending}
          className="rounded-xl bg-white px-3 py-1.5 text-sm font-semibold ring-1 ring-slate-300 hover:bg-slate-50 disabled:opacity-50"
        >
          {rebuild.isPending ? "Đang dựng…" : "Dựng lại chỉ mục"}
        </button>
      </div>
      <ul aria-label="Theo nguồn và loại" className="mt-2 flex flex-wrap gap-1.5 text-xs">
        {Object.entries(status.by_source).map(([source, count]) => (
          <li key={source} className="rounded-full bg-brand-50 px-2.5 py-0.5 font-semibold text-brand-900">
            {SOURCE_LABEL[source] ?? source}: {count}
          </li>
        ))}
        {Object.entries(status.by_kind).map(([kind, count]) => (
          <li key={kind} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-slate-700">
            {KIND_LABEL[kind] ?? kind}: {count}
          </li>
        ))}
      </ul>
      {status.documents.length === 0 ? (
        <p className="mt-2 text-sm text-amber-900">
          Chưa có tài liệu giáo viên: RAG đang dùng nội dung chương (bản nháp do AI soạn, chờ giáo viên
          duyệt). Tải tài liệu ở tab Tài liệu để thêm nguồn.
        </p>
      ) : (
        <table className="mt-3 w-full text-left text-sm">
          <caption className="text-left text-xs font-semibold text-slate-600">
            Tài liệu giáo viên trong kho
          </caption>
          <thead className="text-xs text-slate-500">
            <tr>
              <th className="py-1 pr-3 font-medium">Tài liệu</th>
              <th className="py-1 pr-3 font-medium">Số đoạn</th>
              <th className="py-1 font-medium">Gắn được vào bài</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {status.documents.map((d) => (
              <tr key={d.document_id}>
                <td className="py-1 pr-3">{d.title}</td>
                <td className="py-1 pr-3 tabular-nums">{d.passages}</td>
                <td className="py-1 tabular-nums">{d.tied_to_node}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Search({ status }: { status: RagStatus }) {
  const api = useApi();
  const [query, setQuery] = useState("");
  const [nodeId, setNodeId] = useState("");
  const [mode, setMode] = useState<RagMode>("question");
  const search = useMutation({
    mutationFn: () => api.rag!.search(query.trim(), { nodeId: nodeId || undefined, mode }),
  });
  return (
    <section aria-labelledby="rag-search" className="card p-4">
      <h2 id="rag-search" className="font-bold">
        Thử tra cứu
      </h2>
      <p className="text-sm text-slate-600">
        Gõ một câu như học sinh hỏi: hệ thống chạy đủ 6 bước (phạm vi, từ khóa, ngữ nghĩa, hợp nhất, xếp hạng
        lại theo sư phạm, chọn đoạn) và hiện điểm từng bước.
      </p>
      <form
        className="mt-3 grid gap-3 md:grid-cols-[2fr_1fr_1fr_auto] md:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          if (query.trim()) search.mutate();
        }}
      >
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold">Câu hỏi</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="VD: sao thêm số 0 vào cuối mà số không đổi"
            maxLength={300}
            className="rounded-xl bg-white px-3 py-2 ring-1 ring-slate-300"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold">Học sinh đang ở bài</span>
          <select
            value={nodeId}
            onChange={(event) => setNodeId(event.target.value)}
            className="rounded-xl bg-white px-3 py-2 ring-1 ring-slate-300"
          >
            <option value="">Cả chương</option>
            {status.nodes.map((n) => (
              <option key={n.node_id} value={n.node_id}>
                {n.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold">Ai cần</span>
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value as RagMode)}
            className="rounded-xl bg-white px-3 py-2 ring-1 ring-slate-300"
          >
            <option value="question">Học sinh hỏi</option>
            <option value="teach">Gia sư giảng bài</option>
            <option value="hint">Gia sư gợi ý</option>
          </select>
        </label>
        <button
          type="submit"
          disabled={!query.trim() || search.isPending}
          className="rounded-xl bg-brand-700 px-4 py-2 font-semibold text-white hover:bg-brand-800 disabled:opacity-50"
        >
          Tra cứu
        </button>
      </form>
      {search.isError && (
        <p role="alert" className="mt-3 text-sm text-rose-800">
          Chưa tra cứu được.
        </p>
      )}
      {search.data && <Results found={search.data} />}
    </section>
  );
}

function Results({ found }: { found: RagSearch }) {
  return (
    <div className="mt-4 flex flex-col gap-3">
      <p
        role="status"
        className={`rounded-xl px-3 py-2 text-sm ring-1 ${
          found.grounded
            ? "bg-emerald-50 text-emerald-900 ring-emerald-200"
            : "bg-amber-50 text-amber-900 ring-amber-200"
        }`}
      >
        <span className="font-semibold">
          {found.grounded
            ? "Có căn cứ: gia sư được dựa vào các đoạn này."
            : "Không có căn cứ: gia sư không trả lời từ các đoạn này mà quay về nội dung chính của bài."}
        </span>{" "}
        ({found.grounding}) · {MODE_LABEL[found.mode]} · {found.candidates} đoạn trong phạm vi ·{" "}
        {decimal(found.elapsed_ms, 1)} ms
      </p>
      <ol aria-label="Các đoạn được chọn" className="flex flex-col gap-3">
        {found.results.map((r, i) => (
          <ResultCard key={r.chunk_id} rank={i + 1} result={r} />
        ))}
      </ol>
    </div>
  );
}

function ResultCard({ rank, result }: { rank: number; result: RagResult }) {
  const long = result.text.length > PREVIEW_CHARS;
  const where = [
    KIND_LABEL[result.kind] ?? result.kind,
    SOURCE_LABEL[result.source] ?? result.source,
    result.node_name,
    result.page ? `trang ${result.page}` : null,
    result.approved ? null : "bản nháp",
  ].filter(Boolean);
  return (
    <li className="rounded-xl bg-slate-50 p-3 text-sm">
      <p className="font-semibold">
        {rank}. {result.title}
      </p>
      <p className="text-xs text-slate-500">
        {where.join(" · ")} · <code className="font-mono">{result.chunk_id}</code>
      </p>
      {long ? (
        <details className="mt-1">
          <summary className="cursor-pointer">
            <MathText text={`${result.text.slice(0, PREVIEW_CHARS)}…`} />
          </summary>
          <p className="mt-1 whitespace-pre-line">
            <MathText text={result.text} />
          </p>
        </details>
      ) : (
        <p className="mt-1 whitespace-pre-line">
          <MathText text={result.text} />
        </p>
      )}
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3 lg:grid-cols-6">
        <Signal
          label="Từ khóa (BM25)"
          value={`${decimal(result.bm25, 1)} · hạng ${result.bm25_rank ?? "–"}`}
        />
        <Signal
          label="Ngữ nghĩa (cosine)"
          value={
            result.cosine_rank === null ? "–" : `${decimal(result.cosine, 2)} · hạng ${result.cosine_rank}`
          }
        />
        <Signal label="Cách bài đang học" value={`${result.distance} bước`} />
        <Signal label="Hợp nhất (RRF)" value={decimal(result.fused, 4)} />
        <Signal label="Sau xếp hạng lại" value={decimal(result.final, 4)} />
        <Signal label="Phủ câu hỏi" value={`${Math.round(result.coverage * 100)}%`} />
      </dl>
      {result.reasons.length > 0 && (
        <p className="mt-1 text-xs text-slate-600">Xếp hạng lại: {result.reasons.join(", ")}</p>
      )}
    </li>
  );
}

function Signal({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-semibold tabular-nums">{value}</dd>
    </div>
  );
}
