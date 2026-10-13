import type { ConversationStats } from "../../../api/contract";

const SIGNALS: [string, string][] = [
  ["TEENCODE", "Viết tắt (teen code)"],
  ["EMOJI", "Biểu tượng cảm xúc"],
  ["STRETCHED", "Chữ kéo dài"],
  ["KEYWORD_DUMP", "Dồn nhiều từ khóa"],
  ["O_AS_ZERO", "Chữ o thay số 0"],
  ["LONG", "Tin quá dài"],
  ["UNSTICK", "Gia sư tự gợi ý để khỏi lặp lại"],
];

const INTENTS: [string, string][] = [
  ["help", "Xin giúp, không biết"],
  ["clarify", "Chưa hiểu đề"],
  ["asks_about", "Hỏi nghĩa một từ"],
  ["off_topic", "Nói chuyện ngoài bài"],
  ["affect", "Chán, buồn, tự chê"],
  ["answer_demand", "Đòi đáp án"],
];

function Bars({ rows, data }: { rows: [string, string][]; data: Record<string, number> }) {
  const max = Math.max(1, ...rows.map(([k]) => data[k] ?? 0));
  return (
    <ul className="flex flex-col gap-1.5">
      {rows.map(([key, label]) => {
        const n = data[key] ?? 0;
        return (
          <li key={key} className="grid grid-cols-[11rem_1fr_2.5rem] items-center gap-2 text-sm">
            <span className="text-slate-700">{label}</span>
            <span className="h-3 rounded bg-slate-100">
              <span className="block h-3 rounded bg-brand-600" style={{ width: `${(100 * n) / max}%` }} />
            </span>
            <span className="text-right font-semibold tabular-nums">{n}</span>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * The child's messages as the tutor met them: how the conductor read them (teen code, emoji, a heap of
 * keywords, a tutor unstuck instead of repeating itself), what they were (ADR-019) and the lesson questions
 * the RAG answered or kept for the teacher.
 */
export function ConversationPanel({ stats }: { stats: ConversationStats }) {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <div className="flex flex-col gap-2">
        <h3 className="font-semibold">Con gõ thế nào (bộ điều phối đọc)</h3>
        <Bars rows={SIGNALS} data={stats.signals} />
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="font-semibold">Con nói gì ngoài câu trả lời</h3>
        <Bars rows={INTENTS} data={stats.intents} />
      </div>
      <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4 md:col-span-2">
        {[
          ["Tin nhắn của con", stats.messages],
          ["Lần bấm xin gợi ý", stats.hint_button],
          ["Câu hỏi về bài (RAG)", stats.questions],
          ["Câu hỏi để cô trả lời sau", stats.parked],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg bg-slate-50 p-3">
            <dt className="text-slate-600">{label}</dt>
            <dd className="text-xl font-bold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
