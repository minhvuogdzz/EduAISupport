import { Route, Routes } from "react-router";

import { ParentChildPage, ParentPage } from "./features/parent/ParentPages";
import { SessionPage } from "./features/student/SessionPage";
import { StudentStartPage } from "./features/student/StudentStartPage";
import { ClassPage } from "./features/teacher/ClassPage";
import { StudentReportPage } from "./features/teacher/StudentReportPage";
import { TeacherPage } from "./features/teacher/TeacherPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/student" element={<StudentStartPage />} />
      <Route path="/student/sessions/:sessionId" element={<SessionPage />} />
      <Route path="/parent" element={<ParentPage />} />
      <Route path="/parent/:code" element={<ParentChildPage />} />
      <Route path="/teacher" element={<ClassPage />} />
      <Route path="/teacher/students/:studentId" element={<StudentReportPage />} />
      <Route path="/teacher/sessions" element={<TeacherPage />} />
      <Route path="/teacher/sessions/:sessionId" element={<TeacherPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
