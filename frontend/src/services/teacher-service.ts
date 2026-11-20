import { apiRequest } from "@/services/api-client";
import type {
  TeacherAnalytics,
  TeacherClass,
  TeacherDashboard,
  TeacherResultsPage,
  TeacherStudent,
  TeacherStudentPerformance,
} from "@/types/teacher";

export const teacherService = {
  dashboard: () => apiRequest<TeacherDashboard>("/teacher/dashboard"),
  classes: () => apiRequest<TeacherClass[]>("/teacher/classes"),
  students: (classId?: string) =>
    apiRequest<TeacherStudent[]>(
      `/teacher/students${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`,
    ),
  results: (page = 1) =>
    apiRequest<TeacherResultsPage>(
      `/teacher/results?page=${page}&page_size=25`,
    ),
  studentPerformance: (studentId: string, classId?: string) =>
    apiRequest<TeacherStudentPerformance>(
      `/teacher/students/${encodeURIComponent(studentId)}/performance${
        classId ? `?class_id=${encodeURIComponent(classId)}` : ""
      }`,
    ),
  analytics: () => apiRequest<TeacherAnalytics>("/teacher/analytics"),
};
