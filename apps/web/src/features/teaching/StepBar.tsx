import { TEACHING_STEPS } from "../../components/labels";

/**
 * The seven steps of the teaching cycle (plan v1, 5.2) with the current one marked. UI-1: numbered dots
 * on a line and the current step named once below, so no label wraps over three lines in the side column.
 */
export function StepBar({ step, nodeName }: { step: number | null; nodeName: string | null }) {
  const current = step ? TEACHING_STEPS[step - 1] : null;
  return (
    <nav
      aria-label={nodeName ? `Các bước học bài ${nodeName}` : "Các bước học"}
      className="flex flex-col gap-2"
    >
      {nodeName && <p className="truncate text-sm font-semibold text-brand-900">{nodeName}</p>}
      <ol className="flex items-center">
        {TEACHING_STEPS.map((label, index) => {
          const number = index + 1;
          const isCurrent = number === step;
          const done = step !== null && number < step;
          return (
            <li
              key={label}
              aria-current={isCurrent ? "step" : undefined}
              title={label}
              className="flex flex-1 items-center last:flex-none"
            >
              <span
                aria-hidden="true"
                className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  isCurrent
                    ? "bg-brand-700 text-white ring-4 ring-brand-100"
                    : done
                      ? "bg-brand-100 text-brand-900"
                      : "bg-slate-100 text-slate-500"
                }`}
              >
                {done ? "✓" : number}
              </span>
              <span className="sr-only">
                {label}
                {done ? " (đã qua)" : ""}
              </span>
              {number < TEACHING_STEPS.length && (
                <span
                  aria-hidden="true"
                  className={`mx-1 h-0.5 flex-1 rounded-full ${done ? "bg-brand-200" : "bg-slate-100"}`}
                />
              )}
            </li>
          );
        })}
      </ol>
      {current && (
        <p className="text-sm font-medium text-brand-900" aria-hidden="true">
          {`Bước ${step}/${TEACHING_STEPS.length} · ${current}`}
        </p>
      )}
    </nav>
  );
}
