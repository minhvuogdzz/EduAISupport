import { ApiError, type SubjectOverrides } from "../../client";
import { classOverview, DEMO_STUDENTS, ME, parentView, studentOverview, studentReport } from "./reports";
import { createEnglishSessions, type EnglishSessionOptions } from "./session";
import { UNIT } from "./unit11";

/**
 * The English unit inside the mock API (ENG-7a): what the English pages read until ENG-7b points them at
 * the server. Only the unit of D-T13 exists; asking for another chapter is a 404, as on the server.
 */
export function createEnglishDemo(options: EnglishSessionOptions): SubjectOverrides {
  const { now, latencyMs } = options;
  const wait = () => new Promise<void>((resolve) => setTimeout(resolve, latencyMs));
  const unit = (chapterId: string | undefined) => {
    if (chapterId && chapterId !== UNIT.chapter_id) {
      throw new ApiError(404, "NOT_FOUND", `chapter ${chapterId} not found`);
    }
  };
  return {
    ...createEnglishSessions(options),
    async getMyOverview(chapterId) {
      await wait();
      unit(chapterId);
      return studentOverview(ME, now());
    },
    async getMyChild(chapterId) {
      await wait();
      unit(chapterId);
      return parentView(ME, now());
    },
    async getChildOverview(code, chapterId) {
      await wait();
      unit(chapterId);
      const child = DEMO_STUDENTS.find((s) => s.parent_code === code.toUpperCase());
      if (!child) throw new ApiError(404, "NOT_FOUND", `no child with code ${code}`);
      return parentView(child, now());
    },
    async getClassOverview(chapterId) {
      await wait();
      unit(chapterId);
      return classOverview(now());
    },
    async getStudentReport(studentId, chapterId) {
      await wait();
      unit(chapterId);
      const report = studentReport(studentId, now());
      if (!report) throw new ApiError(404, "NOT_FOUND", `student ${studentId} not found`);
      return report;
    },
    async getTaughtChapters() {
      await wait();
      return [{ ...UNIT, subject: "english" as const }];
    },
    async getTurnAudio() {
      await wait();
      return tone();
    },
  };
}

/** The mock has no recording: a soft 0,6 s tone stands in, so the play button can be tried. */
function tone(): Blob {
  const rate = 8000;
  const samples = Math.round(rate * 0.6);
  const buffer = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(buffer);
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i += 1) view.setUint8(offset + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + samples * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples * 2, true);
  for (let i = 0; i < samples; i += 1) {
    const fade = Math.min(1, i / 400, (samples - i) / 400);
    view.setInt16(44 + i * 2, Math.round(Math.sin((2 * Math.PI * 440 * i) / rate) * 6000 * fade), true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}
