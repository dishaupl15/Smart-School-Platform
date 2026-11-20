import { apiRequest } from "@/services/api-client";
import type {
  AcademicClass,
  Chapter,
  DashboardStats,
  Enrollment,
  Page,
  Person,
  ProvisionedPerson,
  Student,
  StudentDetail,
  Subject,
  Teacher,
  TeacherAssignment,
} from "@/types/admin";

type Query = Record<string, string | number | boolean | undefined>;

function queryString(query: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const result = params.toString();
  return result ? `?${result}` : "";
}

function jsonBody(body: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(body) };
}

function patchBody(body: unknown): RequestInit {
  return { method: "PATCH", body: JSON.stringify(body) };
}

export const adminService = {
  dashboard: () => apiRequest<DashboardStats>("/admin/dashboard/stats"),
  students: (query: Query = {}) =>
    apiRequest<Page<Student>>(`/admin/students${queryString(query)}`),
  student: (id: string) => apiRequest<StudentDetail>(`/admin/students/${id}`),
  createStudent: (body: {
    full_name: string;
    student_identifier: string;
    email?: string;
    phone?: string;
    class_id: string;
  }) => apiRequest<ProvisionedPerson>("/admin/students", jsonBody(body)),
  updateStudent: (id: string, body: Record<string, unknown>) =>
    apiRequest<Person>(`/admin/students/${id}`, patchBody(body)),
  studentStatus: (id: string, is_active: boolean) =>
    apiRequest<Person>(
      `/admin/students/${id}/status`,
      patchBody({ is_active }),
    ),
  teachers: (query: Query = {}) =>
    apiRequest<Page<Teacher>>(`/admin/teachers${queryString(query)}`),
  teacher: (id: string) => apiRequest<Teacher>(`/admin/teachers/${id}`),
  createTeacher: (body: {
    full_name: string;
    teacher_identifier: string;
    email: string;
    phone?: string;
  }) => apiRequest<ProvisionedPerson>("/admin/teachers", jsonBody(body)),
  updateTeacher: (id: string, body: Record<string, unknown>) =>
    apiRequest<Person>(`/admin/teachers/${id}`, patchBody(body)),
  teacherStatus: (id: string, is_active: boolean) =>
    apiRequest<Person>(
      `/admin/teachers/${id}/status`,
      patchBody({ is_active }),
    ),
  classes: (query: Query = {}) =>
    apiRequest<Page<AcademicClass>>(`/admin/classes${queryString(query)}`),
  createClass: (body: {
    name: string;
    grade_number: number;
    academic_year: string;
    section?: string;
  }) => apiRequest<AcademicClass>("/admin/classes", jsonBody(body)),
  updateClass: (id: string, body: Record<string, unknown>) =>
    apiRequest<AcademicClass>(`/admin/classes/${id}`, patchBody(body)),
  classStatus: (id: string, is_active: boolean) =>
    apiRequest<AcademicClass>(
      `/admin/classes/${id}/status`,
      patchBody({ is_active }),
    ),
  assignSubject: (classId: string, subjectId: string) =>
    apiRequest<AcademicClass>(
      `/admin/classes/${classId}/subjects`,
      jsonBody({ subject_id: subjectId }),
    ),
  subjects: (query: Query = {}) =>
    apiRequest<Page<Subject>>(`/admin/subjects${queryString(query)}`),
  createSubject: (body: { name: string; code: string; description?: string }) =>
    apiRequest<Subject>("/admin/subjects", jsonBody(body)),
  updateSubject: (id: string, body: Record<string, unknown>) =>
    apiRequest<Subject>(`/admin/subjects/${id}`, patchBody(body)),
  subjectStatus: (id: string, is_active: boolean) =>
    apiRequest<Subject>(
      `/admin/subjects/${id}/status`,
      patchBody({ is_active }),
    ),
  chapters: (query: Query = {}) =>
    apiRequest<Page<Chapter>>(`/admin/chapters${queryString(query)}`),
  createChapter: (body: {
    class_id: string;
    subject_id: string;
    chapter_number: number;
    title: string;
    description?: string;
  }) => apiRequest<Chapter>("/admin/chapters", jsonBody(body)),
  updateChapter: (id: string, body: Record<string, unknown>) =>
    apiRequest<Chapter>(`/admin/chapters/${id}`, patchBody(body)),
  chapterStatus: (id: string, is_active: boolean) =>
    apiRequest<Chapter>(
      `/admin/chapters/${id}/status`,
      patchBody({ is_active }),
    ),
  enrollments: (query: Query = {}) =>
    apiRequest<Page<Enrollment>>(`/admin/enrollments${queryString(query)}`),
  createEnrollment: (body: {
    student_id: string;
    class_id: string;
    academic_year: string;
  }) => apiRequest<Enrollment>("/admin/enrollments", jsonBody(body)),
  transferEnrollment: (id: string, target_class_id: string) =>
    apiRequest<Enrollment>(
      `/admin/enrollments/${id}/transfer`,
      jsonBody({ target_class_id }),
    ),
  assignments: (query: Query = {}) =>
    apiRequest<Page<TeacherAssignment>>(
      `/admin/teacher-assignments${queryString(query)}`,
    ),
  createAssignment: (body: {
    teacher_id: string;
    class_id: string;
    subject_id: string;
    academic_year: string;
  }) =>
    apiRequest<TeacherAssignment>("/admin/teacher-assignments", jsonBody(body)),
  updateAssignment: (id: string, body: Record<string, unknown>) =>
    apiRequest<TeacherAssignment>(
      `/admin/teacher-assignments/${id}`,
      patchBody(body),
    ),
  deactivateAssignment: (id: string) =>
    apiRequest<void>(`/admin/teacher-assignments/${id}`, { method: "DELETE" }),
};
