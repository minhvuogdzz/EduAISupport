import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApi } from "../../api/apiContext";
import type { TeacherFigure } from "../../api/contract";
import { FigureImage } from "../../components/Figures";

const STATUS: Record<string, string> = {
  AUTO: "Đã trích từ tài liệu",
  APPROVED: "Đã duyệt",
  REVIEW: "Chờ duyệt",
  REJECTED: "Đã bỏ",
  STALE: "Nguồn đã đổi, cần xem lại",
};

/** Image decisions never republish the plan or alter its text approvals. */
export function FigureReview({ chapterId }: { chapterId: string }) {
  const api = useApi();
  const cache = useQueryClient();
  const list = useQuery({
    queryKey: ["teacher-figures", chapterId],
    queryFn: () => api.figures!.all(chapterId),
    enabled: Boolean(api.figures && chapterId),
  });
  const refresh = () => {
    void cache.invalidateQueries({ queryKey: ["teacher-figures", chapterId] });
    void cache.invalidateQueries({ queryKey: ["figures"] });
  };
  const decide = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" | "undo" }) =>
      api.figures!.decide(id, action),
    onSuccess: refresh,
  });
  const replace = useMutation({
    mutationFn: ({ figure, file }: { figure: TeacherFigure; file: File }) =>
      api.figures!.replace(file, {
        chapterId,
        questionId: figure.question_id,
        order: figure.order,
        tag: figure.tag,
      }),
    onSuccess: refresh,
  });
  if (!api.figures) return null;
  const busy = decide.isPending || replace.isPending;
  return (
    <details className="card my-3 p-4">
      <summary className="cursor-pointer font-bold">
        Hình minh họa{list.data ? ` · ${list.data.length} hình` : ""}
      </summary>
      <p className="mt-2 text-sm text-slate-600">
        Duyệt, bỏ hoặc thay từng hình. Việc này giữ nguyên câu chữ và các nội dung đã duyệt của bài học.
      </p>
      {list.isPending ? (
        <p role="status">Đang tải hình…</p>
      ) : list.isError ? (
        <p role="alert">Chưa tải được danh sách hình.</p>
      ) : null}
      {(decide.isError || replace.isError) && (
        <p role="alert" className="mt-2 text-sm text-rose-700">
          Chưa lưu được hình. Ảnh thay thế cần là PNG, JPG hoặc WebP, tối đa 5 MB.
        </p>
      )}
      {list.data?.length === 0 && (
        <p className="mt-2 text-sm text-slate-600">Chưa có hình được trích từ tài liệu cho chương này.</p>
      )}
      <ul className="mt-3 grid gap-4 md:grid-cols-2">
        {list.data?.map((figure) => (
          <li key={figure.figure_id} className="rounded-xl border border-slate-200 p-3">
            <p className="text-sm font-semibold">
              {figure.question_id} · hình {figure.order}
            </p>
            <p className="text-xs text-slate-600">
              {STATUS[figure.status] ?? figure.status} ·{" "}
              {figure.shown ? "Học sinh đang thấy" : "Chưa hiện cho học sinh"}
              {figure.page ? ` · trang ${figure.page}` : ""}
            </p>
            <FigureImage figure={figure} />
            <p className="text-xs text-slate-600">{figure.alt}</p>
            <div className="mt-2 flex flex-wrap gap-2 text-sm">
              <button
                type="button"
                disabled={busy || figure.status === "APPROVED"}
                aria-label={`Duyệt hình ${figure.question_id}`}
                className="rounded-lg bg-brand-700 px-3 py-2 font-semibold text-white disabled:opacity-40"
                onClick={() => decide.mutate({ id: figure.figure_id, action: "approve" })}
              >
                Duyệt hình
              </button>
              <button
                type="button"
                disabled={busy || figure.status === "REJECTED"}
                aria-label={`Bỏ hình ${figure.question_id}`}
                className="rounded-lg px-3 py-2 text-rose-700 disabled:opacity-40"
                onClick={() => decide.mutate({ id: figure.figure_id, action: "reject" })}
              >
                Bỏ hình
              </button>
              {figure.decided_by && (
                <button
                  type="button"
                  disabled={busy}
                  aria-label={`Hoàn tác hình ${figure.question_id}`}
                  className="rounded-lg px-3 py-2 underline"
                  onClick={() => decide.mutate({ id: figure.figure_id, action: "undo" })}
                >
                  Hoàn tác
                </button>
              )}
              <label
                className={`rounded-lg border border-slate-300 px-3 py-2 ${busy ? "opacity-40" : "cursor-pointer"}`}
              >
                Thay hình
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="sr-only"
                  aria-label={`Thay hình ${figure.question_id}`}
                  disabled={busy}
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    if (file) replace.mutate({ figure, file });
                    event.currentTarget.value = "";
                  }}
                />
              </label>
            </div>
          </li>
        ))}
      </ul>
    </details>
  );
}
