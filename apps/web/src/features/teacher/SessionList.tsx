import { Link } from "react-router";

import type { LifecycleState, SessionSummary } from "../../api/contract";
import { Chip, type ChipTone } from "../../components/Chip";
import { LIFECYCLE_LABEL } from "../../components/labels";
import { formatViDateTime } from "../../lib/viNumber";

const LIFECYCLE_TONE: Partial<Record<LifecycleState, ChipTone>> = {
  ACTIVE: "teal",
  COMPLETED: "emerald",
  INTERRUPTED: "amber",
  FAILED: "rose",
};

export function LifecycleChip({ state }: { state: LifecycleState }) {
  return <Chip tone={LIFECYCLE_TONE[state] ?? "slate"}>{LIFECYCLE_LABEL[state]}</Chip>;
}

export function SessionList({
  sessions,
  selectedId,
}: {
  sessions: SessionSummary[];
  selectedId: string | null;
}) {
  if (sessions.length === 0) return <p className="text-slate-600">Chưa có buổi học nào.</p>;
  return (
    <nav aria-label="Danh sách buổi học">
      <ul className="flex flex-col gap-2">
        {sessions.map((session) => {
          const selected = session.session_id === selectedId;
          return (
            <li key={session.session_id}>
              <Link
                to={`/teacher/sessions/${session.session_id}`}
                aria-current={selected ? "page" : undefined}
                className={`flex flex-col gap-1 rounded-2xl p-3 ring-1 ${
                  selected ? "bg-teal-50 ring-2 ring-teal-600" : "bg-white ring-slate-200 hover:ring-teal-400"
                }`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-lg font-semibold">{session.student_display_name}</span>
                  <LifecycleChip state={session.lifecycle_state} />
                </span>
                <span className="text-sm text-slate-600">
                  {session.started_at ? formatViDateTime(session.started_at) : "Chưa bắt đầu"} ·{" "}
                  {session.progress.items_done}/{session.progress.items_total}{" "}
                  {session.mode === "CHAPTER" ? "bài" : "câu"}
                </span>
                {session.misconception_ids.length > 0 && (
                  <span className="flex flex-wrap gap-1">
                    {session.misconception_ids.map((id) => (
                      <Chip key={id} tone="rose" mono>
                        {id}
                      </Chip>
                    ))}
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
