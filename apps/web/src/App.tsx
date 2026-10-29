import { useEffect, type ReactNode } from "react";
import { Route, Routes, useLocation } from "react-router";

import type { AccountKind } from "./api/contract";
import { AdminPage } from "./features/admin/AdminPage";
import { AuthGate, RequireKind } from "./features/auth/AuthGate";
import { ParentChildPage, ParentPage } from "./features/parent/ParentPages";
import { SessionPage } from "./features/student/SessionPage";
import { StudentStartPage } from "./features/student/StudentStartPage";
import { ClassPage } from "./features/teacher/ClassPage";
import { DocumentPage, DocumentsPage } from "./features/teacher/DocumentsPage";
import { ChapterContentPage, LessonsPage } from "./features/teacher/LessonsPage";
import { PlanReviewPage } from "./features/teacher/PlanReviewPage";
import { RagPage } from "./features/teacher/RagPage";
import { StudentReportPage } from "./features/teacher/StudentReportPage";
import { TeacherPage } from "./features/teacher/TeacherPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";

function only(kind: AccountKind, page: ReactNode) {
  return <RequireKind kind={kind}>{page}</RequireKind>;
}

/** The introduction stays public; each account area keeps its protected route. */
function Home() {
  return <HomePage />;
}

export function App() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    // Each area opens at its heading; in-page anchors keep the browser's smooth scroll.
    if (!hash && window.scrollY > 0) window.scrollTo({ top: 0, behavior: "instant" });
  }, [pathname, hash]);
  return (
    <AuthGate>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Home />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/student" element={only("STUDENT", <StudentStartPage />)} />
        <Route path="/student/sessions/:sessionId" element={only("STUDENT", <SessionPage />)} />
        <Route path="/parent" element={only("PARENT", <ParentPage />)} />
        <Route path="/parent/:code" element={only("PARENT", <ParentChildPage />)} />
        <Route path="/teacher" element={only("TEACHER", <ClassPage />)} />
        <Route path="/teacher/students/:studentId" element={only("TEACHER", <StudentReportPage />)} />
        <Route path="/teacher/sessions" element={only("TEACHER", <TeacherPage />)} />
        <Route path="/teacher/sessions/:sessionId" element={only("TEACHER", <TeacherPage />)} />
        <Route path="/teacher/lessons" element={only("TEACHER", <LessonsPage />)} />
        <Route path="/teacher/lessons/:chapterId" element={only("TEACHER", <ChapterContentPage />)} />
        <Route path="/teacher/plans/:chapterId" element={only("TEACHER", <PlanReviewPage />)} />
        <Route path="/teacher/documents" element={only("TEACHER", <DocumentsPage />)} />
        <Route path="/teacher/documents/:documentId" element={only("TEACHER", <DocumentPage />)} />
        <Route path="/teacher/rag" element={only("TEACHER", <RagPage />)} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AuthGate>
  );
}
