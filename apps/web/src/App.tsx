import type { ReactNode } from "react";
import { Route, Routes } from "react-router";

import type { AccountKind } from "./api/contract";
import { AuthGate, RequireKind } from "./features/auth/AuthGate";
import { ParentChildPage, ParentPage } from "./features/parent/ParentPages";
import { SessionPage } from "./features/student/SessionPage";
import { StudentStartPage } from "./features/student/StudentStartPage";
import { ClassPage } from "./features/teacher/ClassPage";
import { StudentReportPage } from "./features/teacher/StudentReportPage";
import { TeacherPage } from "./features/teacher/TeacherPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";

function only(kind: AccountKind, page: ReactNode) {
  return <RequireKind kind={kind}>{page}</RequireKind>;
}

export function App() {
  return (
    <AuthGate>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/student" element={only("STUDENT", <StudentStartPage />)} />
        <Route path="/student/sessions/:sessionId" element={only("STUDENT", <SessionPage />)} />
        <Route path="/parent" element={only("PARENT", <ParentPage />)} />
        <Route path="/parent/:code" element={only("PARENT", <ParentChildPage />)} />
        <Route path="/teacher" element={only("TEACHER", <ClassPage />)} />
        <Route path="/teacher/students/:studentId" element={only("TEACHER", <StudentReportPage />)} />
        <Route path="/teacher/sessions" element={only("TEACHER", <TeacherPage />)} />
        <Route path="/teacher/sessions/:sessionId" element={only("TEACHER", <TeacherPage />)} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AuthGate>
  );
}
