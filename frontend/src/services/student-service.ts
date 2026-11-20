import { apiRequest } from "@/services/api-client";
import type {
  StudentChapterDetail,
  StudentDashboard,
  StudentEnrollmentChoice,
  StudentProfile,
  StudentSubjectDetail,
  StudentSubjectSummary,
} from "@/types/student";
import type {
  QuizAnalytics,
  QuizAttempt,
  QuizCurrent,
  QuizHistory,
  QuizResult,
} from "@/types/student-quiz";

export interface QuizHistoryFilters {
  subject_id?: string;
  chapter_id?: string;
  date_from?: string;
  date_to?: string;
  page: number;
  page_size: number;
}

export const studentService = {
  dashboard: () => apiRequest<StudentDashboard>("/student/dashboard"),
  enrollments: () =>
    apiRequest<StudentEnrollmentChoice[]>("/student/enrollments"),
  profile: () => apiRequest<StudentProfile>("/student/profile"),
  subjects: (classId?: string) =>
    apiRequest<StudentSubjectSummary[]>(
      `/student/subjects${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`,
    ),
  subject: (id: string, classId?: string) =>
    apiRequest<StudentSubjectDetail>(
      `/student/subjects/${id}${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`,
    ),
  chapter: (id: string, classId?: string) =>
    apiRequest<StudentChapterDetail>(
      `/student/chapters/${id}${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`,
    ),
  currentQuiz: (chapterId: string, classId?: string) =>
    apiRequest<QuizCurrent>(
      `/student/chapters/${chapterId}/quiz/current${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`,
    ),
  startQuiz: (chapterId: string, languageCode: string, classId?: string) =>
    apiRequest<QuizAttempt | QuizResult>(
      `/student/chapters/${chapterId}/quiz/start${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`,
      {
        method: "POST",
        body: JSON.stringify({ language_code: languageCode }),
      },
    ),
  saveQuizAnswer: (
    attemptId: string,
    questionId: string,
    selectedOptionId: string,
  ) =>
    apiRequest<QuizAttempt | QuizResult>(
      `/student/quiz/attempts/${attemptId}/answers/${questionId}`,
      {
        method: "PUT",
        body: JSON.stringify({ selected_option_id: selectedOptionId }),
      },
    ),
  submitQuiz: (attemptId: string) =>
    apiRequest<QuizResult>(`/student/quiz/attempts/${attemptId}/submit`, {
      method: "POST",
    }),
  quizHistory: (filters: QuizHistoryFilters) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, String(value));
    });
    return apiRequest<QuizHistory>(`/student/quiz/history?${params}`);
  },
  quizAnalytics: () => apiRequest<QuizAnalytics>("/student/quiz/analytics"),
  quizResult: (attemptId: string) =>
    apiRequest<QuizResult>(`/student/quiz/attempts/${attemptId}/result`),
};
