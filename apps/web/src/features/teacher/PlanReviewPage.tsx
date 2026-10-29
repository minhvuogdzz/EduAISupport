import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";

import { useApi } from "../../api/apiContext";
import type { ContentItem, ContentNode, PlanItemNote, TeachingPlanReview } from "../../api/contract";
import { AppShell } from "../../components/AppShell";
import { FiguresProvider } from "../../components/Figures";
import { FigureReview } from "./FigureReview";
import { MathText } from "../../components/MathText";
import { TeacherHeader } from "./TeacherHeader";

/**
 * The teacher reviews the plan built from their documents (INGEST-4): approve each period, fix what was
 * misread, keep or rewrite what Qwen drafted, then publish it for the tutor to teach.
 */

const STATUS: Record<string, { label: string; tone: string }> = {
  VERIFIED: { label: "đáp án đã kiểm", tone: "bg-emerald-50 text-emerald-900 ring-emerald-200" },
  TEACHER: { label: "cô đã sửa đáp án", tone: "bg-emerald-50 text-emerald-900 ring-emerald-200" },
  REVIEW: { label: "xem lại lời giải", tone: "bg-amber-50 text-amber-900 ring-amber-200" },
  UNCHECKED: { label: "chưa kiểm được", tone: "bg-slate-100 text-slate-800 ring-slate-200" },
  CONFLICT: { label: "đáp án mâu thuẫn", tone: "bg-rose-50 text-rose-900 ring-rose-200" },
  DISPUTED: { label: "số đọc chưa chắc", tone: "bg-rose-50 text-rose-900 ring-rose-200" },
};

const STAGES: [string, string][] = [
  ["checks", "Kiểm tra hiểu"],
  ["completion", "Cùng làm"],
  ["practice", "Luyện tập"],
  ["transfer", "Vận dụng"],
];

function Notice({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="card p-5">
      {children}
    </p>
  );
}

function Chip({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, tone: "bg-slate-100 text-slate-800 ring-slate-200" };
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${s.tone}`}>{s.label}</span>;
}

/**
 * A value the teacher may rewrite: shown as text, edited in place, saved as a decision. An empty value is
 * not a decision the API takes ("an edit needs a value"): where a field may be left empty, `onClear` says
 * what that means (the field goes back to its default); elsewhere an empty save changes nothing.
 */
function Editable({
  label,
  value,
  onSave,
  onClear,
  multiline = false,
  hint,
}: {
  label: string;
  value: string;
  onSave: (value: string) => void;
  onClear?: () => void;
  multiline?: boolean;
  hint?: string;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  if (draft === null) {
    return (
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm">
          <span className="text-slate-500">{label}: </span>
          {value ? <MathText text={value} /> : <em className="text-amber-800">chưa có</em>}
        </p>
        <button
          type="button"
          onClick={() => setDraft(value)}
          className="shrink-0 rounded-lg px-2 py-1 text-xs font-semibold text-brand-800 hover:bg-brand-50"
          aria-label={`Sửa ${label.toLowerCase()}`}
        >
          Sửa
        </button>
      </div>
    );
  }
  return (
    <form
      className="flex flex-col gap-1"
      onSubmit={(event) => {
        event.preventDefault();
        if (draft.trim()) onSave(draft.trim());
        else if (value && onClear) onClear();
        setDraft(null);
      }}
    >
      <label className="text-sm text-slate-600">
        {label}
        {multiline ? (
          <textarea
            value={draft}
            rows={3}
            onChange={(event) => setDraft(event.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm"
          />
        ) : (
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm"
          />
        )}
      </label>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
      <div className="flex gap-2">
        <button type="submit" className="rounded-lg bg-brand-700 px-3 py-1 text-xs font-semibold text-white">
          Lưu
        </button>
        <button type="button" onClick={() => setDraft(null)} className="rounded-lg px-3 py-1 text-xs">
          Hủy
        </button>
      </div>
    </form>
  );
}

export function PlanReviewPage() {
  const api = useApi();
  const queryClient = useQueryClient();
  const { chapterId = "" } = useParams();
  const key = ["plan-review", chapterId];
  const plan = useQuery({
    queryKey: key,
    queryFn: () => api.plans!.view(chapterId),
    enabled: api.plans !== undefined,
    retry: false,
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: key });
  const decide = useMutation({
    mutationFn: (d: { target: string; action: "approve" | "reject" | "edit"; value?: unknown }) =>
      api.plans!.decide(chapterId, d.target, d.action, d.value),
    onSuccess: refresh,
  });
  const undo = useMutation({
    mutationFn: (target: string) => api.plans!.undo(chapterId, target),
    onSuccess: refresh,
  });
  const build = useMutation({ mutationFn: () => api.plans!.build(chapterId), onSuccess: refresh });
  const publish = useMutation({ mutationFn: () => api.plans!.publish(chapterId), onSuccess: refresh });
  const actions: Actions = {
    decide: (target, action, value) => decide.mutate({ target, action, value }),
    undo: (target) => undo.mutate(target),
    busy: decide.isPending || undo.isPending,
  };

  let body: ReactNode;
  if (!api.plans) body = <Notice>Trang duyệt cần máy chủ thật: chạy bản demo bằng lệnh make demo.</Notice>;
  else if (plan.isPending) body = <Notice>Đang tải phương án…</Notice>;
  else if (plan.isError)
    body = (
      <Notice>
        Chưa có phương án dạy dựng từ tài liệu cho chương này.{" "}
        <button
          type="button"
          className="font-semibold text-brand-800 underline"
          onClick={() => build.mutate()}
        >
          Dựng ngay
        </button>
      </Notice>
    );
  else
    body = (
      <Review
        plan={plan.data}
        actions={actions}
        onBuild={() => build.mutate()}
        onPublish={() => publish.mutate()}
        publishError={publish.error ? String(publish.error.message) : null}
        error={decide.error ? String(decide.error.message) : null}
      />
    );
  return (
    <FiguresProvider chapterId={chapterId} who="teacher">
      <AppShell>
        <title>Duyệt phương án · Giáo viên · Monkey Edu</title>
        <TeacherHeader
          title={plan.data ? `Duyệt phương án: ${plan.data.content.title}` : "Duyệt phương án"}
        />
        <div className="mx-auto max-w-7xl px-4 pb-10">
          <Link to="/teacher/lessons" className="mb-3 inline-block text-sm text-brand-800 hover:underline">
            ← Các chương
          </Link>
          <FigureReview chapterId={chapterId} />
          {body}
        </div>
      </AppShell>
    </FiguresProvider>
  );
}

interface Actions {
  decide: (target: string, action: "approve" | "reject" | "edit", value?: unknown) => void;
  undo: (target: string) => void;
  busy: boolean;
}

function Review({
  plan,
  actions,
  onBuild,
  onPublish,
  publishError,
  error,
}: {
  plan: TeachingPlanReview;
  actions: Actions;
  onBuild: () => void;
  onPublish: () => void;
  publishError: string | null;
  error: string | null;
}) {
  const nodes = plan.content.nodes;
  const [selected, setSelected] = useState(nodes[0]?.node_id ?? "");
  const node = nodes.find((n) => n.node_id === selected) ?? nodes[0];
  const blockers = plan.review.blockers;
  return (
    <div className="flex flex-col gap-4">
      <section className="card flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="text-sm">
          <p className="font-semibold">
            {plan.current ? `Gia sư đang dạy bản ${plan.current}` : "Bản nháp, gia sư chưa dạy"} ·{" "}
            {plan.review.approved_nodes.length}/{nodes.length} bài đã duyệt
          </p>
          <p className="text-slate-600">
            Gia sư Buddy soạn {plan.drafted.hints} gợi ý và {plan.drafted.parts} phần khác: cô duyệt hoặc sửa
            trước khi dạy.
          </p>
          {blockers.length > 0 && (
            <details className="mt-1">
              <summary className="cursor-pointer text-amber-900">
                Còn {blockers.length} việc trước khi phát hành
              </summary>
              <ul className="mt-1 list-disc pl-5 text-xs text-slate-700">
                {blockers.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </details>
          )}
          {(publishError || error) && (
            <p role="alert" className="mt-1 text-sm text-rose-700">
              {publishError ?? error}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onBuild}
            className="rounded-xl px-3 py-2 text-sm font-semibold ring-1 ring-slate-300"
          >
            Dựng lại từ tài liệu
          </button>
          <button
            type="button"
            onClick={onPublish}
            disabled={blockers.length > 0}
            className="rounded-xl bg-brand-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            Phát hành cho gia sư dạy
          </button>
        </div>
      </section>
      <div className="grid items-start gap-4 lg:grid-cols-[15rem_1fr]">
        <nav aria-label="Các bài trong phương án" className="card p-3 lg:sticky lg:top-20">
          <ol className="flex flex-col gap-1">
            {nodes.map((n, i) => {
              const approved = plan.review.approved_nodes.includes(n.node_id);
              return (
                <li key={n.node_id}>
                  <button
                    type="button"
                    aria-current={n.node_id === node?.node_id ? "true" : undefined}
                    onClick={() => setSelected(n.node_id)}
                    className={`w-full rounded-xl px-3 py-2 text-left text-sm ${
                      n.node_id === node?.node_id ? "bg-indigo-700 text-white" : "hover:bg-slate-50"
                    }`}
                  >
                    <span className="font-semibold">
                      {approved ? "✓ " : ""}
                      {i + 1}. {n.name}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>
        {node && <NodeReview node={node} plan={plan} actions={actions} />}
      </div>
      {plan.left_out.length > 0 && <LeftOut plan={plan} actions={actions} />}
    </div>
  );
}

function NodeReview({
  node,
  plan,
  actions,
}: {
  node: ContentNode;
  plan: TeachingPlanReview;
  actions: Actions;
}) {
  const approved = plan.review.approved_nodes.includes(node.node_id);
  const target = `node:${node.node_id}`;
  const edit = (path: string, value: string) => actions.decide(`${target}/${path}`, "edit", value);
  return (
    <article className="flex flex-col gap-3" aria-label={node.name}>
      <section className="card flex flex-wrap items-start justify-between gap-2 p-4">
        <div>
          <h2 className="text-lg font-bold">{node.name}</h2>
          <ul className="mt-1 text-xs text-slate-600">
            {(plan.sources[node.node_id] ?? []).map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
        <button
          type="button"
          disabled={actions.busy}
          onClick={() => (approved ? actions.undo(target) : actions.decide(target, "approve"))}
          className={`rounded-xl px-3 py-2 text-sm font-semibold ${
            approved ? "ring-1 ring-slate-300" : "bg-emerald-700 text-white"
          }`}
        >
          {approved ? "Bỏ duyệt bài này" : "Duyệt bài này"}
        </button>
      </section>
      <section className="card flex flex-col gap-3 p-4">
        <h3 className="font-bold">Kiến thức và gợi ý dạy học</h3>
        <p className="text-sm text-slate-600">
          Duyệt kiến thức và ý cần kiểm tra, không duyệt một kịch bản hội thoại cố định. Gia sư có thể đổi
          cách giảng, ví dụ và diễn đạt câu hỏi cùng ý theo điều học sinh đang vướng. Đáp án và tiêu chí chấm
          bài tập được quản lý riêng ở phần bài tập.
        </p>
        {node.theory.map((t) => (
          <div key={t.id} className="rounded-xl bg-slate-50 p-3">
            <p className="text-xs text-slate-500">
              {t.id} · {t.representation}
            </p>
            <Editable
              label="Nội dung kiến thức / gợi ý tổ chức dạy"
              value={t.text}
              multiline
              onSave={(v) => edit(`theory/${t.id}/text`, v)}
            />
            <Editable
              label="Câu hỏi tham khảo (ý cần kiểm tra)"
              value={t.ask}
              onSave={(v) => edit(`theory/${t.id}/ask`, v)}
            />
            <Editable
              label="Ý giải thích tham khảo"
              value={t.reply ?? ""}
              onSave={(v) => edit(`theory/${t.id}/reply`, v)}
            />
            <Editable
              label="Ví dụ cách học sinh diễn đạt đúng ý"
              value={(t.accept ?? []).join(" · ")}
              multiline
              hint="Mỗi ví dụ một dòng. Không giới hạn câu trả lời; khi Gia sư Buddy khả dụng, gia sư đối chiếu ý nghĩa với kiến thức đã duyệt."
              onSave={(v) => edit(`theory/${t.id}/accept`, v)}
            />
          </div>
        ))}
        {node.theory.length < 2 && (
          <button
            type="button"
            onClick={() => edit("theory/T2/text", "…")}
            className="self-start text-sm font-semibold text-brand-800 underline"
          >
            Thêm cách giảng thứ hai
          </button>
        )}
      </section>
      <section className="card flex flex-col gap-2 p-4">
        <h3 className="font-bold">Quy tắc và con nói lại</h3>
        <Editable label="Quy tắc" value={node.method.rule} multiline onSave={(v) => edit("method/rule", v)} />
        <Editable
          label="Câu hỏi con nói lại"
          value={node.retell.prompt}
          onSave={(v) => edit("explain/prompt", v)}
        />
        <Editable
          label="Ý chính"
          value={node.retell.key_ideas.map((idea) => idea.join(" / ")).join(" · ")}
          multiline
          hint="Mỗi ý một dòng; các cách nói của cùng một ý cách nhau bằng dấu /."
          onSave={(v) => edit("explain/key_ideas", v)}
        />
        <VerifyReview node={node} plan={plan} actions={actions} />
      </section>
      <MistakesReview node={node} plan={plan} actions={actions} />
      {STAGES.map(([stage, label]) => {
        const items = node.items.filter((it) => it.stage === label);
        return items.length === 0 ? null : (
          <section key={stage} className="card flex flex-col gap-2 p-4">
            <h3 className="font-bold">
              {label} ({items.length})
            </h3>
            {items.map((item) => (
              <ItemReview
                key={item.item_id}
                item={item}
                note={plan.items[item.item_id]}
                plan={plan}
                actions={actions}
              />
            ))}
          </section>
        );
      })}
    </article>
  );
}

/** FIX-3: the "vì sao" of the period, asked after a right answer to one of its items. */
function VerifyReview({
  node,
  plan,
  actions,
}: {
  node: ContentNode;
  plan: TeachingPlanReview;
  actions: Actions;
}) {
  const target = `node:${node.node_id}/verify/prompt`;
  const decision = plan.decisions[target];
  const ai = plan.ai_verify?.includes(node.node_id) && decision?.action !== "edit";
  return (
    <div className="flex flex-col gap-1 rounded-xl bg-slate-50 p-2">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <span className="font-semibold">Hỏi sau câu đúng</span>
        {ai && <span className="rounded bg-violet-100 px-1 text-violet-900">Gia sư Buddy soạn</span>}
        {node.verify_prompt && (
          <button
            type="button"
            onClick={() => actions.decide(target, "reject")}
            className="font-semibold text-rose-700"
          >
            Loại câu hỏi vì sao
          </button>
        )}
      </div>
      <Editable
        label="Câu hỏi vì sao"
        value={node.verify_prompt ?? ""}
        hint="Gia sư hỏi câu này khi con làm đúng một bài của tiết. Không ghi con số: câu dùng chung cho mọi bài. Để trống thì gia sư hỏi câu chung."
        onSave={(v) => actions.decide(target, "edit", v)}
        onClear={() => actions.decide(target, "reject")}
      />
    </div>
  );
}

/** FIX-3: the mistakes of the period and their counterexamples, which the teacher edits or removes. */
function MistakesReview({
  node,
  plan,
  actions,
}: {
  node: ContentNode;
  plan: TeachingPlanReview;
  actions: Actions;
}) {
  const mistakes = plan.content.misconceptions.filter((m) => m.kc_id === node.node_id);
  if (mistakes.length === 0) return null;
  return (
    <section className="card flex flex-col gap-2 p-4">
      <h3 className="font-bold">Lỗi sai hay gặp và phản ví dụ</h3>
      {mistakes.map((m) => {
        const target = `misconception:${m.id}/counter_examples`;
        return (
          <div key={m.id} className="rounded-xl bg-slate-50 p-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="font-mono">{m.id}</span>
              <span className="font-semibold text-slate-800">{m.name}</span>
              {m.counter_examples.length > 0 && (
                <button
                  type="button"
                  onClick={() => actions.decide(target, "reject")}
                  className="ml-auto font-semibold text-rose-700"
                >
                  Bỏ phản ví dụ
                </button>
              )}
            </div>
            <Editable
              label={`Phản ví dụ của ${m.id}`}
              value={m.counter_examples.join("\n")}
              multiline
              hint="Mỗi phản ví dụ một dòng, kết thúc bằng một câu hỏi; không nói ra đáp án của bài nào."
              onSave={(v) => actions.decide(target, "edit", v)}
            />
          </div>
        );
      })}
    </section>
  );
}

function ItemReview({
  item,
  note,
  plan,
  actions,
}: {
  item: ContentItem;
  note: PlanItemNote | undefined;
  plan: TeachingPlanReview;
  actions: Actions;
}) {
  const id = item.item_id;
  return (
    <div className="rounded-xl border border-slate-200 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-slate-500">{id}</span>
        {note && <Chip status={note.status} />}
        {note?.page ? <span className="text-xs text-slate-500">trang {note.page}</span> : null}
        <span className="ml-auto flex gap-1">
          <select
            aria-label={`Chuyển mức câu ${id}`}
            value=""
            onChange={(event) =>
              event.target.value && actions.decide(`item:${id}/stage`, "edit", event.target.value)
            }
            className="rounded-lg border border-slate-300 px-1 text-xs"
          >
            <option value="">Chuyển mức…</option>
            {STAGES.map(([stage, label]) => (
              <option key={stage} value={stage}>
                {label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => actions.decide(`item:${id}`, "reject")}
            className="rounded-lg px-2 text-xs font-semibold text-rose-700 hover:bg-rose-50"
          >
            Bỏ câu này
          </button>
        </span>
      </div>
      <p className="mt-1">
        <MathText text={item.stem} questionId={item.item_id} />
      </p>
      <Editable
        label="Đáp án"
        value={item.answer}
        onSave={(v) => actions.decide(`item:${id}/answer`, "edit", v)}
      />
      {note && note.findings.length > 0 && (
        <p className="text-xs text-amber-900">Bộ kiểm: {note.findings.map((f) => f.detail).join("; ")}</p>
      )}
      <ul className="mt-2 flex flex-col gap-1">
        {[1, 2, 3].map((level) => {
          const hint = item.hints.find((h) => h.level === level);
          const target = `hint:${id}:H${level}`;
          const decision = plan.decisions[target];
          const ai = note?.ai_hints.includes(level) && decision?.action !== "edit";
          return (
            <li key={level} className="rounded-lg bg-slate-50 p-2">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="font-semibold">H{level}</span>
                {ai && <span className="rounded bg-violet-100 px-1 text-violet-900">Gia sư Buddy soạn</span>}
                {decision?.action === "approve" && <span className="text-emerald-800">đã duyệt</span>}
                {hint && decision?.action !== "approve" && (
                  <button
                    type="button"
                    onClick={() => actions.decide(target, "approve")}
                    className="font-semibold text-emerald-800"
                  >
                    Duyệt
                  </button>
                )}
                {hint && (
                  <button
                    type="button"
                    onClick={() => actions.decide(target, "reject")}
                    className="font-semibold text-rose-700"
                  >
                    Loại
                  </button>
                )}
              </div>
              <Editable
                label={`Gợi ý H${level}`}
                value={hint?.text ?? ""}
                onSave={(v) => actions.decide(target, "edit", v)}
              />
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function LeftOut({ plan, actions }: { plan: TeachingPlanReview; actions: Actions }) {
  return (
    <section className="card flex flex-col gap-2 p-4" aria-labelledby="left-out-title">
      <h2 id="left-out-title" className="font-bold">
        Câu chưa được dạy ({plan.left_out.length})
      </h2>
      <p className="text-sm text-slate-600">
        Đáp án đọc từ tài liệu bị lệch hoặc mâu thuẫn, hoặc giáo án chưa dùng câu này. Cô sửa đáp án để đưa
        câu vào bài.
      </p>
      {plan.left_out.map((it) => (
        <div key={it.item_id} className="rounded-xl border border-rose-200 p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-slate-500">{it.item_id}</span>
            <Chip status={it.status} />
            {it.page ? <span className="text-xs text-slate-500">trang {it.page}</span> : null}
          </div>
          <p className="mt-1">
            <MathText text={it.stem} questionId={it.item_id} />
          </p>
          {it.findings.length > 0 && (
            <p className="text-xs text-rose-800">Bộ kiểm: {it.findings.map((f) => f.detail).join("; ")}</p>
          )}
          <Editable
            label="Đề"
            value={it.stem}
            multiline
            onSave={(v) => actions.decide(`item:${it.item_id}/stem`, "edit", v)}
          />
          <Editable
            label="Đáp án"
            value={it.answer}
            onSave={(v) => actions.decide(`item:${it.item_id}/answer`, "edit", v)}
          />
        </div>
      ))}
    </section>
  );
}
