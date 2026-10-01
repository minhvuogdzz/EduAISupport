import { Route, Routes } from "react-router";

import { SessionPage } from "./features/student/SessionPage";
import { StudentStartPage } from "./features/student/StudentStartPage";
import { TeacherPage } from "./features/teacher/TeacherPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/student" element={<StudentStartPage />} />
      <Route path="/student/sessions/:sessionId" element={<SessionPage />} />
      <Route path="/teacher" element={<TeacherPage />} />
      <Route path="/teacher/sessions/:sessionId" element={<TeacherPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
