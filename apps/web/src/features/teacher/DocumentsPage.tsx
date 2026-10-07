import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { useApi } from "../../api/apiContext";
import type { DocumentKind, TeacherDocument } from "../../api/contract";
import { AppShell } from "../../components/AppShell";
import { formatViDateTime } from "../../lib/viNumber";
import { TeacherHeader } from "./TeacherHeader";

const KIND_LABEL: Record<DocumentKind, string> = {
  SGK: "Sách giáo khoa",
  GIAO_AN: "Giáo án",
  BAI_TAP: "Phiếu bài tập",
  DE_KIEM_TRA: "Đề kiểm tra",
  KHAC: "Khác",
};

const STATUS_LABEL: Record<TeacherDocument["status"], string> = {
  READ: "Đã đọc",
  NEEDS_OCR: "Cần đọc ảnh (OCR)",
  FAILED: "Không đọc được",
};

const STATUS_TONE: Record<TeacherDocument["status"], string> = {
  READ: "bg-emerald-50 text-emerald-900 ring-emerald-200",
  NEEDS_OCR: "bg-amber-50 text-amber-900 ring-amber-200",
  FAILED: "bg-rose-50 text-rose-900 ring-rose-200",
};

const ACCEPT = ".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp";

function size(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="card p-5">
      {children}
    </p>
  );
}

/** The teacher's documents (DOC-1): what they upload is read at once and becomes a source of the RAG. */
export function DocumentsPage() {
  const api = useApi();
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.library!.list(),
    enabled: api.library !== undefined,
    retry: false,
  });
  let body: ReactNode;
  if (!api.library) {
    body = <Notice>Thư viện tài liệu cần máy chủ thật: chạy bản demo bằng lệnh make demo.</Notice>;
  } else if (documents.isPending) {
    body = <Notice>Đang tải danh sách tài liệu…</Notice>;
  } else if (documents.isError) {
    body = <Notice>Chưa tải được danh sách tài liệu.</Notice>;
  } else {
    body = (
      <div className="flex flex-col gap-5">
        <UploadForm />
        <section aria-labelledby="docs-title" className="card p-5">
          <h2 id="docs-title" className="text-lg font-bold">
            Tài liệu đã tải lên
          </h2>
          {documents.data.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600">Chưa có tài liệu nào.</p>
          ) : (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-slate-600">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Tên</th>
                    <th className="py-2 pr-3 font-medium">Loại</th>
                    <th className="py-2 pr-3 font-medium">Chương</th>
                    <th className="py-2 pr-3 font-medium">Trang</th>
                    <th className="py-2 pr-3 font-medium">Số chữ</th>
                    <th className="py-2 pr-3 font-medium">Trạng thái</th>
                    <th className="py-2 font-medium">Tải lên</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {documents.data.map((d) => (
                    <tr key={d.document_id}>
                      <td className="py-2 pr-3">
                        <Link
                          to={`/teacher/documents/${encodeURIComponent(d.document_id)}`}
                          className="font-medium text-brand-800 hover:underline"
                        >
                          {d.title}
                        </Link>
                        <span className="block text-xs text-slate-500">
                          {d.filename} · {size(d.size)}
                        </span>
                      </td>
                      <td className="py-2 pr-3">{KIND_LABEL[d.kind]}</td>
                      <td className="py-2 pr-3">{d.chapter_id ?? "—"}</td>
                      <td className="py-2 pr-3 tabular-nums">{d.pages}</td>
                      <td className="py-2 pr-3 tabular-nums">{d.chars.toLocaleString("vi-VN")}</td>
                      <td className="py-2 pr-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${STATUS_TONE[d.status]}`}
                        >
                          {STATUS_LABEL[d.status]}
                        </span>
                      </td>
                      <td className="py-2 whitespace-nowrap">{formatViDateTime(d.uploaded_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    );
  }
  return (
    <AppShell>
      <title>Tài liệu · Giáo viên · CAVAT</title>
      <TeacherHeader title="Tài liệu của giáo viên" />
      <div className="mx-auto max-w-7xl px-4 pb-10">{body}</div>
    </AppShell>
  );
}

function UploadForm() {
  const api = useApi();
  const queryClient = useQueryClient();
  const chapters = useQuery({ queryKey: ["chapters"], queryFn: () => api.library!.chapters(), retry: false });
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<DocumentKind>("SGK");
  const [chapterId, setChapterId] = useState("");
  const upload = useMutation({
    mutationFn: () => api.library!.upload(file!, { title, kind, chapterId }),
    onSuccess: () => {
      setFile(null);
      setTitle("");
      if (fileRef.current) fileRef.current.value = "";
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });
  return (
    <section aria-labelledby="upload-title" className="card brand-gradient p-5">
      <h2 id="upload-title" className="text-lg font-bold">
        Tải tài liệu lên
      </h2>
      <p className="text-sm text-slate-700">
        Sách giáo khoa, giáo án, phiếu bài tập có đáp án: hệ thống đọc chữ ngay và dùng làm nguồn cho gia sư
        (RAG).
      </p>
      <form
        className="mt-3 grid gap-3 md:grid-cols-[1.4fr_1fr_0.8fr_1fr_auto] md:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          if (file) upload.mutate();
        }}
      >
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold">File (PDF, DOCX, ảnh…)</span>
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPT}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="rounded-xl bg-white p-2 ring-1 ring-slate-300"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold">Tên tài liệu</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={file?.name ?? "VD: SGK Toán 5, Bài 8"}
            className="rounded-xl bg-white px-3 py-2 ring-1 ring-slate-300"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold">Loại</span>
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value as DocumentKind)}
            className="rounded-xl bg-white px-3 py-2 ring-1 ring-slate-300"
          >
            {(Object.keys(KIND_LABEL) as DocumentKind[]).map((k) => (
              <option key={k} value={k}>
                {KIND_LABEL[k]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold">Chương</span>
          <select
            value={chapterId}
            onChange={(event) => setChapterId(event.target.value)}
            className="rounded-xl bg-white px-3 py-2 ring-1 ring-slate-300"
          >
            <option value="">Chưa chọn</option>
            {(chapters.data ?? []).map((c) => (
              <option key={c.chapter_id} value={c.chapter_id}>
                {c.title}
              </option>
            ))}
            <option value="math-g5-area-triangle-trapezoid">Diện tích hình tam giác, hình thang</option>
          </select>
        </label>
        <button
          type="submit"
          disabled={!file || upload.isPending}
          className="rounded-xl bg-brand-700 px-4 py-2 font-semibold text-white hover:bg-brand-800 disabled:opacity-50"
        >
          {upload.isPending ? "Đang đọc…" : "Tải lên"}
        </button>
      </form>
      {upload.isError && (
        <p role="alert" className="mt-2 text-sm text-rose-700">
          Chưa tải lên được: {upload.error.message}
        </p>
      )}
      {upload.isSuccess && (
        <p role="status" className="mt-2 text-sm text-emerald-800">
          Đã tải lên «{upload.data.title}»: {STATUS_LABEL[upload.data.status].toLowerCase()},{" "}
          {upload.data.chars.toLocaleString("vi-VN")} chữ.
        </p>
      )}
    </section>
  );
}

/** One document: its text as the RAG will read it, the original file, deletion. */
export function DocumentPage() {
  const api = useApi();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { documentId = "" } = useParams();
  const document = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => api.library!.get(documentId),
    enabled: api.library !== undefined,
    retry: false,
  });
  const remove = useMutation({
    mutationFn: () => api.library!.remove(documentId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      await navigate("/teacher/documents");
    },
  });
  async function openOriginal() {
    const blob = await api.library!.original(documentId);
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }
  let body: ReactNode;
  if (!api.library) body = <Notice>Thư viện tài liệu cần máy chủ thật.</Notice>;
  else if (document.isPending) body = <Notice>Đang tải tài liệu…</Notice>;
  else if (document.isError) body = <Notice>Không tìm thấy tài liệu này.</Notice>;
  else {
    const d = document.data;
    body = (
      <div className="flex flex-col gap-4">
        <section className="card flex flex-wrap items-center justify-between gap-3 p-5">
          <div>
            <p className="text-sm text-slate-600">
              {KIND_LABEL[d.kind]} · {d.chapter_id ?? "chưa chọn chương"} · {d.filename} · {size(d.size)} ·{" "}
              {d.pages} trang · đọc bằng {d.method || "—"}
            </p>
            <span
              className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${STATUS_TONE[d.status]}`}
            >
              {STATUS_LABEL[d.status]}
            </span>
            {d.error && <p className="mt-1 text-sm text-rose-700">{d.error}</p>}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void openOriginal()}
              className="rounded-xl bg-white px-3 py-2 text-sm font-semibold ring-1 ring-slate-300 hover:bg-slate-50"
            >
              Mở file gốc
            </button>
            <button
              type="button"
              onClick={() => {
                if (window.confirm(`Xóa tài liệu «${d.title}»? File gốc cũng bị xóa.`)) remove.mutate();
              }}
              className="rounded-xl bg-white px-3 py-2 text-sm font-semibold text-rose-700 ring-1 ring-rose-200 hover:bg-rose-50"
            >
              Xóa
            </button>
          </div>
        </section>
        <section aria-labelledby="text-title" className="card p-5">
          <h2 id="text-title" className="font-bold">
            Chữ đọc được ({d.chars.toLocaleString("vi-VN")} ký tự)
          </h2>
          <p className="text-xs text-slate-500">Đây là phần gia sư sẽ tra cứu (RAG).</p>
          <pre className="mt-2 max-h-[60vh] overflow-auto rounded-xl bg-slate-50 p-3 font-sans text-sm whitespace-pre-wrap">
            {d.text || "(chưa có chữ)"}
          </pre>
        </section>
      </div>
    );
  }
  return (
    <AppShell>
      <title>Tài liệu · Giáo viên · CAVAT</title>
      <TeacherHeader title={document.data?.title ?? "Tài liệu"} />
      <div className="mx-auto max-w-7xl px-4 pb-10">
        <Link to="/teacher/documents" className="mb-3 inline-block text-sm text-brand-800 hover:underline">
          ← Tất cả tài liệu
        </Link>
        {body}
      </div>
    </AppShell>
  );
}
