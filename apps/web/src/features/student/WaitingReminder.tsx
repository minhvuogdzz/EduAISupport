import { useEffect, useState } from "react";

/** A gentle, local check-in. Silence is never submitted as an answer or graded. */
export function WaitingReminder({ enabled, turnKey }: { enabled: boolean; turnKey: string }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let reminded = false;
    function reset() {
      clearTimeout(timer);
      setVisible(false);
      if (!enabled || reminded || document.visibilityState === "hidden") return;
      timer = setTimeout(() => {
        // A child composing a response still owns the turn.
        if (document.querySelector<HTMLTextAreaElement>("textarea")?.value.trim()) return;
        reminded = true;
        setVisible(true);
      }, 45_000);
    }
    reset();
    document.addEventListener("input", reset);
    document.addEventListener("pointerdown", reset);
    document.addEventListener("visibilitychange", reset);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("input", reset);
      document.removeEventListener("pointerdown", reset);
      document.removeEventListener("visibilitychange", reset);
    };
  }, [enabled, turnKey]);
  return visible && enabled ? (
    <p role="status" className="rounded-2xl bg-sky-50 px-4 py-3 text-brand-900">
      Con đang suy nghĩ hay cần cô giúp một chút? Con cứ từ từ; nếu chưa rõ, con nói chỗ mình đang vướng nhé.
    </p>
  ) : null;
}
