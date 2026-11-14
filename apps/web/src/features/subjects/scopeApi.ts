import type { SessionApi } from "../../api/client";
import type { Subject } from "../../api/contract";
import { PROFILES } from "./profile";

/**
 * The API as the pages of one subject see it. Math gets the shared API untouched. English gets:
 * - with the mock: the mock's English demo (fixed data of Unit 11 and a small tutor session, ENG-7a);
 * - with the real API: the same endpoints, asked for the unit (`?chapter=`) and with the lists kept to
 *   English. The server still decides the subject of a session (rule S1): the client only names a chapter
 *   the server lists, as it does for math. ENG-7b checks this against the real endpoints.
 */
export function scopeApi(api: SessionApi, subject: Subject): SessionApi {
  if (subject === "math") return api;
  if (api.englishDemo) return { ...api, ...api.englishDemo };
  const unit = PROFILES.english.defaultChapter;
  const mine = <T extends { subject?: Subject }>(items: T[]) => items.filter((i) => i.subject === subject);
  return {
    ...api,
    createDemoSession: (input) => api.createDemoSession({ ...input, chapter_id: input.chapter_id ?? unit }),
    listMySessions: async () => mine(await api.listMySessions()),
    listSessions: async () => mine(await api.listSessions()),
    getMyOverview: api.getMyOverview && ((chapter) => api.getMyOverview!(chapter ?? unit)),
    getMyChild: api.getMyChild && ((chapter) => api.getMyChild!(chapter ?? unit)),
    getChildOverview:
      api.getChildOverview && ((code, chapter) => api.getChildOverview!(code, chapter ?? unit)),
    getClassOverview: api.getClassOverview && ((chapter) => api.getClassOverview!(chapter ?? unit)),
    getStudentReport:
      api.getStudentReport && ((studentId, chapter) => api.getStudentReport!(studentId, chapter ?? unit)),
    getTaughtChapters: api.getTaughtChapters && (async () => mine(await api.getTaughtChapters!())),
  };
}
