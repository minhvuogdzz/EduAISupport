import { useMemo, type ReactNode } from "react";

import { ApiContext, useApi } from "../../api/apiContext";
import type { Subject } from "../../api/contract";
import { PROFILES } from "./profile";
import { scopeApi } from "./scopeApi";
import { SubjectContext } from "./subjectContext";

/**
 * The pages inside see one subject: its words (`useSubject`) and its data (`useApi`). The shared pages of
 * math run unchanged inside an English scope, so English adds no page of its own where math has one.
 */
export function SubjectScope({ subject, children }: { subject: Subject; children: ReactNode }) {
  const api = useApi();
  const scoped = useMemo(() => scopeApi(api, subject), [api, subject]);
  return (
    <SubjectContext value={PROFILES[subject]}>
      <ApiContext value={scoped}>{children}</ApiContext>
    </SubjectContext>
  );
}
