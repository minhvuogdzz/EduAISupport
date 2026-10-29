import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";

import { useApi } from "../../api/apiContext";
import type { ChapterContent, ContentItem, ContentNode } from "../../api/contract";
import { AppShell } from "../../components/AppShell";
import { FiguresProvider } from "../../components/Figures";
import { FigureReview } from "./FigureReview";
import { MathText } from "../../components/MathText";
import { TeacherHeader } from "./TeacherHeader";

const STATUS_LABEL: Record<string, string> = {
  DRAFT: "Bản nháp, chờ giáo viên duyệt",
  APPROVED: "Đã duyệt",
  PUBLISHED: "Đang dùng",
  ARCHIVED: "Lưu trữ",
};

function Notice({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="card p-5">
      {children}
    </p>
  );
}

/** The plan built from the teacher's documents (INGEST-4): where the teacher reviews and publishes it. */
function PlanLink({ chapterId }: { chapterId: string }) {
  return (
    <Link
      to={`/teacher/plans/${encodeURIComponent(chapterId)}`}
      className="mt-3 inline-block rounded-xl bg-indigo-700 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-800"
    >
      Phương án dạy từ tài liệu: xem và duyệt
    </Link>
  );
}

/** The chapters the tutor teaches (DOC-1): the teacher reads every node, question and answer. */
export function LessonsPage() {
  const api = useApi();
  const chapters = useQuery({
    queryKey: ["chapters"],
    queryFn: () => api.library!.chapters(),
    enabled: api.library !== undefined,
    retry: false,
  });
  let body: ReactNode;
  if (!api.library) body = <Notice>Nội dung bài cần máy chủ thật: chạy bản demo bằng lệnh make demo.</Notice>;
  else if (chapters.isPending) body = <Notice>Đang tải các chương…</Notice>;
  else if (chapters.isError) body = <Notice>Chưa tải được các chương.</Notice>;
  else
    body = (
      <ul className="grid gap-4 md:grid-cols-2">
        {chapters.data.map((c) => (
          <li key={c.chapter_id} className="card p-5">
            <Link
              to={`/teacher/lessons/${encodeURIComponent(c.chapter_id)}`}
              className="block hover:underline"
            >
              <span className="block text-lg font-bold">{c.title}</span>
              <span className="mt-1 block text-sm text-slate-600">
                {c.nodes} bài · {c.items} câu hỏi · {STATUS_LABEL[c.status] ?? c.status}
              </span>
            </Link>
            <PlanLink chapterId={c.chapter_id} />
          </li>
        ))}
        {!chapters.data.some((c) => c.chapter_id === "math-g5-area-triangle-trapezoid") && (
          <li className="card p-5 text-sm text-slate-600">
            <span className="block font-bold text-slate-800">Diện tích hình tam giác, hình thang</span>
            <PlanLink chapterId="math-g5-area-triangle-trapezoid" />
          </li>
        )}
      </ul>
    );
  return (
    <AppShell>
      <title>Bài học · Giáo viên · Monkey Edu</title>
      <TeacherHeader title="Nội dung bài học" />
      <div className="mx-auto max-w-7xl px-4 pb-10">{body}</div>
    </AppShell>
  );
}

/** One chapter, node by node: theory and its question, method, examples, questions with answers. */
export function ChapterContentPage() {
  const api = useApi();
  const { chapterId = "" } = useParams();
  const content = useQuery({
    queryKey: ["chapter-content", chapterId],
    queryFn: () => api.library!.chapter(chapterId),
    enabled: api.library !== undefined,
    retry: false,
  });
  return (
    <FiguresProvider chapterId={chapterId} who="teacher">
      <AppShell>
        <title>Bài học · Giáo viên · Monkey Edu</title>
        <TeacherHeader title={content.data?.title ?? "Bài học"} />
        <div className="mx-auto max-w-7xl px-4 pb-10">
          <Link to="/teacher/lessons" className="mb-3 inline-block text-sm text-brand-800 hover:underline">
            ← Các chương
          </Link>
          <FigureReview chapterId={chapterId} />
          {content.isPending ? (
            <Notice>Đang tải nội dung…</Notice>
          ) : content.isError ? (
            <Notice>Không tìm thấy chương này.</Notice>
          ) : (
            <Chapter content={content.data} />
          )}
        </div>
      </AppShell>
    </FiguresProvider>
  );
}

function Chapter({ content }: { content: ChapterContent }) {
  const [selected, setSelected] = useState(content.nodes[0]?.node_id ?? "");
  const node = content.nodes.find((n) => n.node_id === selected) ?? content.nodes[0];
  const misName = new Map(content.misconceptions.map((m) => [m.id, m.name]));
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-slate-600">
        {STATUS_LABEL[content.status] ?? content.status} · phiên bản {content.version} · nguồn{" "}
        <code className="font-mono text-xs">{content.source}</code>
      </p>
      <div className="grid items-start gap-4 lg:grid-cols-[16rem_1fr]">
        <nav aria-label="Các bài trong chương" className="card p-3 lg:sticky lg:top-20">
          <ol className="flex flex-col gap-1">
            {content.nodes.map((n, i) => (
              <li key={n.node_id}>
                <button
                  type="button"
                  aria-current={n.node_id === node?.node_id ? "true" : undefined}
                  onClick={() => setSelected(n.node_id)}
                  className={`w-full rounded-xl px-3 py-2 text-left text-sm ${
                    n.node_id === node?.node_id ? "bg-brand-700 text-white" : "hover:bg-slate-50"
                  }`}
                >
                  <span className="font-semibold">
                    {i + 1}. {n.name}
                  </span>
                  <span className="block text-xs opacity-80">
                    {n.layer === "BASIC" ? "Khái niệm" : "Vận dụng"} · {n.items.length} câu
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </nav>
        {node && <NodeContent node={node} misName={misName} />}
      </div>
    </div>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card p-4" aria-label={title}>
      <h3 className="mb-2 font-bold">{title}</h3>
      {children}
    </section>
  );
}

function NodeContent({ node, misName }: { node: ContentNode; misName: Map<string, string> }) {
  const stages = [...new Set(node.items.map((i) => i.stage))];
  return (
    <article aria-labelledby="node-title" className="flex flex-col gap-3">
      <header className="card p-4">
        <h2 id="node-title" className="text-xl font-bold">
          {node.name}
        </h2>
        <p className="text-sm text-slate-700">{node.description}</p>
        <p className="mt-1 text-xs text-slate-500">Qua bài khi điểm M ≥ {node.pass_rule.min_mastery}</p>
      </header>

      <Block title="Lý thuyết (các cách giảng)">
        <p className="text-sm text-slate-600">
          Đây là căn cứ kiến thức và ví dụ tham khảo. Gia sư diễn đạt linh hoạt trong bài đang học; học sinh
          không phải nói giống câu mẫu. Tiêu chí chấm bài tập được giữ riêng.
        </p>
        <ol className="flex flex-col gap-3">
          {node.theory.map((t) => (
            <li key={t.id} className="rounded-xl bg-slate-50 p-3 text-sm">
              <p className="text-xs font-semibold text-slate-500">
                {t.id} · {t.representation}
              </p>
              <p className="mt-1">
                <MathText text={t.text} />
              </p>
              <p className="mt-1">
                <span className="font-semibold">Câu hỏi tham khảo: </span>
                <MathText text={t.ask} />
              </p>
              {t.accept.length > 0 && (
                <p className="mt-1">
                  <span className="font-semibold">Ví dụ trả lời đúng ý: </span>
                  {t.accept.join(" · ")}
                </p>
              )}
              {t.reply && (
                <p className="mt-1">
                  <span className="font-semibold">Ý giải thích tham khảo: </span>
                  <MathText text={t.reply} />
                </p>
              )}
            </li>
          ))}
        </ol>
      </Block>

      <Block title="Phương pháp">
        <p className="text-sm font-medium">
          <MathText text={node.method.rule} />
        </p>
        <ol className="mt-1 list-decimal pl-5 text-sm">
          {node.method.steps.map((s) => (
            <li key={s}>
              <MathText text={s} />
            </li>
          ))}
        </ol>
      </Block>

      {node.worked_examples.length > 0 && (
        <Block title="Cô làm mẫu">
          {node.worked_examples.map((w) => (
            <div key={w.id} className="mb-2 rounded-xl bg-slate-50 p-3 text-sm last:mb-0">
              <p className="font-semibold">
                <MathText text={w.problem} />
              </p>
              <ol className="mt-1 list-decimal pl-5">
                {w.steps.map((s) => (
                  <li key={s}>
                    <MathText text={s} />
                  </li>
                ))}
              </ol>
              <p className="mt-1 font-semibold text-emerald-800">
                Đáp số: <MathText text={w.answer} />
              </p>
            </div>
          ))}
        </Block>
      )}

      <Block title="Con nói lại">
        <p className="text-sm">{node.retell.prompt}</p>
        <p className="mt-1 text-sm">
          <span className="font-semibold">Ý chính cần có: </span>
          {node.retell.key_ideas.map((idea) => idea[0]).join(" · ")}
        </p>
      </Block>

      {stages.map((stage) => (
        <Block key={stage} title={`Câu hỏi · ${stage}`}>
          <ol className="flex flex-col gap-3">
            {node.items
              .filter((i) => i.stage === stage)
              .map((item) => (
                <ItemCard key={item.item_id} item={item} misName={misName} />
              ))}
          </ol>
        </Block>
      ))}

      {node.home_tip && (
        <Block title="Gợi ý cho phụ huynh">
          <p className="text-sm">{node.home_tip}</p>
        </Block>
      )}
    </article>
  );
}

function ItemCard({ item, misName }: { item: ContentItem; misName: Map<string, string> }) {
  const wrong = Object.entries(item.wrong_answers);
  return (
    <li className="rounded-xl bg-slate-50 p-3 text-sm">
      <p className="text-xs font-semibold text-slate-500">
        {item.item_id} · mức {item.cognitive_level} · độ khó {item.difficulty}
      </p>
      <p className="mt-1 font-medium">
        <MathText text={item.stem} questionId={item.item_id} />
      </p>
      <p className="mt-1 text-emerald-800">
        <span className="font-semibold">Đáp án: </span>
        <MathText text={item.answer} />
      </p>
      {item.hints.length > 0 && (
        <details className="mt-1">
          <summary className="cursor-pointer text-slate-700">Thang gợi ý ({item.hints.length})</summary>
          <ol className="mt-1 flex flex-col gap-0.5 pl-1">
            {item.hints.map((h) => (
              <li key={`${h.level}-${h.target}`}>
                <span className="font-mono text-xs text-slate-500">
                  H{h.level} {h.target}
                </span>{" "}
                <MathText text={h.text} />
              </li>
            ))}
          </ol>
        </details>
      )}
      {item.worked_solution.length > 0 && (
        <details className="mt-1">
          <summary className="cursor-pointer text-slate-700">Lời giải từng bước</summary>
          <ol className="mt-1 list-decimal pl-5">
            {item.worked_solution.map((s) => (
              <li key={s}>
                <MathText text={s} />
              </li>
            ))}
          </ol>
        </details>
      )}
      {wrong.length > 0 && (
        <p className="mt-1 text-amber-900">
          <span className="font-semibold">Lỗi sai dự đoán: </span>
          {wrong.map(([answer, mis]) => `${answer} → ${misName.get(mis) ?? mis}`).join("; ")}
        </p>
      )}
    </li>
  );
}
