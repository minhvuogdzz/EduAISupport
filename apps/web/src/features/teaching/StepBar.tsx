import { TEACHING_STEPS } from "../../components/labels";

/** The seven steps of the teaching cycle (plan v1, 5.2) with the current one marked. */
export function StepBar({ step, nodeName }: { step: number | null; nodeName: string | null }) {
  return (
    <nav
      aria-label={nodeName ? `Các bước học bài ${nodeName}` : "Các bước học"}
      className="flex flex-col gap-2"
    >
      {nodeName && <p className="text-base font-semibold text-teal-900">{nodeName}</p>}
      <ol className="grid grid-cols-7 gap-1">
        {TEACHING_STEPS.map((label, index) => {
          const number = index + 1;
          const current = number === step;
          const done = step !== null && number < step;
          return (
            <li
              key={label}
              aria-current={current ? "step" : undefined}
              className="flex flex-col items-center gap-1 text-center"
            >
              <span
                aria-hidden="true"
                className={`flex size-8 items-center justify-center rounded-full text-sm font-semibold ${
                  current
                    ? "bg-teal-700 text-white ring-4 ring-teal-200"
                    : done
                      ? "bg-teal-100 text-teal-900"
                      : "bg-slate-100 text-slate-500"
                }`}
              >
                {done ? "✓" : number}
              </span>
              <span
                className={`text-xs leading-tight ${current ? "font-semibold text-teal-900" : "text-slate-600"}`}
              >
                {label}
                {done && <span className="sr-only"> (đã qua)</span>}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
