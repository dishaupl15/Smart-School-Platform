export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Person {
  id: string;
  full_name: string;
  identifier: string;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Enrollment {
  id: string;
  student_id: string;
  student_name: string;
  student_identifier: string;
  class_id: string;
  class_name: string;
  grade_number: number;
  section: string | null;
  academic_year: string;
  is_active: boolean;
  created_at: string;
}

export interface StudentEnrollment {
  id: string;
  class_id: string;
  class_name: string;
  grade_number: number;
  section: string | null;
  academic_year: string;
  is_active: boolean;
}

export interface Student extends Person {
  enrollment: StudentEnrollment | null;
}

export interface StudentDetail extends Person {
  current_enrollment: StudentEnrollment | null;
  enrollments: StudentEnrollment[];
}

export interface TeacherAssignment {
  id: string;
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
  academic_year: string;
  is_active: boolean;
  teacher_id?: string;
  teacher_name?: string;
  teacher_identifier?: string;
  created_at?: string;
}

export interface Teacher extends Person {
  assignments: TeacherAssignment[];
}

export interface ClassSubject {
  id: string;
  name: string;
  code: string;
  is_active: boolean;
}

export interface AcademicClass {
  id: string;
  name: string;
  grade_number: number;
  academic_year: string;
  section: string | null;
  is_active: boolean;
  student_count: number;
  subjects: ClassSubject[];
  created_at: string;
}

export interface SubjectClass {
  id: string;
  name: string;
  grade_number: number;
  section: string | null;
  academic_year: string;
}

export interface Subject {
  id: string;
  name: string;
  code: string;
  description: string | null;
  is_active: boolean;
  classes: SubjectClass[];
  created_at: string;
}

export interface Chapter {
  id: string;
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
  chapter_number: number;
  title: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface DashboardStats {
  active_students: number;
  active_teachers: number;
  classes: number;
  subjects: number;
  chapters: number;
  active_enrollments: number;
  unenrolled_active_students: number;
  recent_students: Person[];
  recent_teachers: Person[];
}

export interface ProvisionedPerson extends Person {
  temporary_password: string;
}
