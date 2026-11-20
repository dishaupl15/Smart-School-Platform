import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AppShell } from "@/layouts/AppShell";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { AuthenticatedHome } from "@/pages/AuthenticatedHome";
import { LoginPage } from "@/pages/LoginPage";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AdminDashboardPage } from "@/pages/admin/AdminDashboardPage";
import {
  StudentChapterDetailPage,
  StudentDashboardPage,
  StudentLearningPlaceholderPage,
  StudentProfilePage,
  StudentSubjectDetailPage,
  StudentSubjectsPage,
} from "@/pages/student/StudentPages";
import { StudentQuizPage } from "@/pages/student/StudentQuizPage";
import {
  StudentQuizHistoryPage,
  StudentQuizResultPage,
} from "@/pages/student/StudentQuizHistoryPage";
import {
  AdminPersonDetailPage,
  AdminPeoplePage,
} from "@/pages/admin/AdminPeoplePage";
import {
  AdminChaptersPage,
  AdminClassesPage,
  AdminSubjectsPage,
} from "@/pages/admin/AdminAcademicPages";
import {
  AdminAssignmentsPage,
  AdminEnrollmentsPage,
} from "@/pages/admin/AdminOperationsPages";
const TeacherDashboardPage = lazy(() =>
  import("@/pages/teacher/TeacherPages").then((module) => ({
    default: module.TeacherDashboardPage,
  })),
);
const TeacherClassesPage = lazy(() =>
  import("@/pages/teacher/TeacherPages").then((module) => ({
    default: module.TeacherClassesPage,
  })),
);
const TeacherStudentsPage = lazy(() =>
  import("@/pages/teacher/TeacherPages").then((module) => ({
    default: module.TeacherStudentsPage,
  })),
);
const TeacherStudentPerformancePage = lazy(() =>
  import("@/pages/teacher/TeacherPages").then((module) => ({
    default: module.TeacherStudentPerformancePage,
  })),
);
const TeacherResultsPage = lazy(() =>
  import("@/pages/teacher/TeacherPages").then((module) => ({
    default: module.TeacherResultsPage,
  })),
);
const TeacherAnalyticsPage = lazy(() =>
  import("@/pages/teacher/TeacherPages").then((module) => ({
    default: module.TeacherAnalyticsPage,
  })),
);

function TeacherPageFallback() {
  return (
    <div className="admin-loading" role="status">
      Loading teacher workspace…
    </div>
  );
}

function teacherPage(element: ReactNode) {
  return <Suspense fallback={<TeacherPageFallback />}>{element}</Suspense>;
}
const QuestionBankDashboardPage = lazy(() =>
  import("@/pages/admin/QuestionBankPages").then((module) => ({
    default: module.QuestionBankDashboardPage,
  })),
);
const QuestionCreatePage = lazy(() =>
  import("@/pages/admin/QuestionBankPages").then((module) => ({
    default: module.QuestionCreatePage,
  })),
);
const QuestionDetailPage = lazy(() =>
  import("@/pages/admin/QuestionBankPages").then((module) => ({
    default: module.QuestionDetailPage,
  })),
);
const QuestionImportPage = lazy(() =>
  import("@/pages/admin/QuestionBankPages").then((module) => ({
    default: module.QuestionImportPage,
  })),
);
const QuestionListPage = lazy(() =>
  import("@/pages/admin/QuestionBankPages").then((module) => ({
    default: module.QuestionListPage,
  })),
);

function QuestionBankFallback() {
  return (
    <div className="admin-loading" role="status">
      Loading question bank…
    </div>
  );
}

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/forbidden",
    element: (
      <main className="error-screen">
        <h1>Access denied</h1>
        <p>Your account does not have permission to view this page.</p>
      </main>
    ),
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    errorElement: <NotFoundPage />,
    children: [
      {
        index: true,
        element: <AuthenticatedHome />,
      },
      {
        path: "admin",
        element: <ProtectedRoute roles={["ADMIN"]} />,
        children: [
          { index: true, element: <AdminDashboardPage /> },
          {
            path: "question-bank",
            element: (
              <Suspense fallback={<QuestionBankFallback />}>
                <QuestionBankDashboardPage />
              </Suspense>
            ),
          },
          {
            path: "questions",
            element: (
              <Suspense fallback={<QuestionBankFallback />}>
                <QuestionListPage />
              </Suspense>
            ),
          },
          {
            path: "questions/new",
            element: (
              <Suspense fallback={<QuestionBankFallback />}>
                <QuestionCreatePage />
              </Suspense>
            ),
          },
          {
            path: "questions/import",
            element: (
              <Suspense fallback={<QuestionBankFallback />}>
                <QuestionImportPage />
              </Suspense>
            ),
          },
          {
            path: "questions/:id",
            element: (
              <Suspense fallback={<QuestionBankFallback />}>
                <QuestionDetailPage />
              </Suspense>
            ),
          },
          { path: "students", element: <AdminPeoplePage kind="students" /> },
          {
            path: "students/:id",
            element: <AdminPersonDetailPage kind="students" />,
          },
          { path: "teachers", element: <AdminPeoplePage kind="teachers" /> },
          {
            path: "teachers/:id",
            element: <AdminPersonDetailPage kind="teachers" />,
          },
          { path: "classes", element: <AdminClassesPage /> },
          { path: "subjects", element: <AdminSubjectsPage /> },
          { path: "chapters", element: <AdminChaptersPage /> },
          { path: "enrollments", element: <AdminEnrollmentsPage /> },
          { path: "assignments", element: <AdminAssignmentsPage /> },
        ],
      },
      {
        path: "student",
        element: <ProtectedRoute roles={["STUDENT"]} />,
        children: [
          { index: true, element: <StudentDashboardPage /> },
          { path: "subjects", element: <StudentSubjectsPage /> },
          {
            path: "subjects/:subjectId",
            element: <StudentSubjectDetailPage />,
          },
          {
            path: "chapters/:chapterId",
            element: <StudentChapterDetailPage />,
          },
          {
            path: "chapters/:chapterId/quiz",
            element: <StudentQuizPage />,
          },
          { path: "quiz/history", element: <StudentQuizHistoryPage /> },
          {
            path: "quiz/history/:attemptId",
            element: <StudentQuizResultPage />,
          },
          { path: "learning", element: <StudentLearningPlaceholderPage /> },
          { path: "profile", element: <StudentProfilePage /> },
        ],
      },
      {
        path: "teacher",
        element: <ProtectedRoute roles={["TEACHER"]} />,
        children: [
          {
            index: true,
            element: teacherPage(<TeacherDashboardPage />),
          },
          {
            path: "classes",
            element: teacherPage(<TeacherClassesPage />),
          },
          {
            path: "classes/:classId/students",
            element: teacherPage(<TeacherStudentsPage />),
          },
          {
            path: "students",
            element: teacherPage(<TeacherStudentsPage />),
          },
          {
            path: "students/:studentId/performance",
            element: teacherPage(<TeacherStudentPerformancePage />),
          },
          {
            path: "results",
            element: teacherPage(<TeacherResultsPage />),
          },
          {
            path: "analytics",
            element: teacherPage(<TeacherAnalyticsPage />),
          },
        ],
      },
      {
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
