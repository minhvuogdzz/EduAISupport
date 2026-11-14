import { createContext, useContext } from "react";

import { MATH_PROFILE, type SubjectProfile } from "./profile";

/** The subject of the page being shown. Outside a `SubjectScope` it is math, as every page was before. */
export const SubjectContext = createContext<SubjectProfile>(MATH_PROFILE);

export function useSubject(): SubjectProfile {
  return useContext(SubjectContext);
}
