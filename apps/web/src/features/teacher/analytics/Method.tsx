import type { ReactNode } from "react";

/** How a number is computed (framework section, DI): folded away so the page stays light to read. */
export function Method({ children }: { children: ReactNode }) {
  return (
    <details className="text-xs text-slate-500">
      <summary className="cursor-pointer select-none hover:text-slate-700">Cách tính</summary>
      <p className="mt-1">{children}</p>
    </details>
  );
}
