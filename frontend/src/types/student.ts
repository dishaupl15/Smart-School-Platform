export interface StudentEnrollmentContext {
  class_id: string;
  class_name: string;
  grade_number: number;
  section: string | null;
  academic_year: string;
}

export type StudentEnrollmentChoice = StudentEnrollmentContext;

export interface StudentProfile {
  full_name: string;
  identifier: string;
  email: string | null;
  phone: string | null;
  school_name: string;
  enrollment: StudentEnrollmentContext;
}

export interface StudentSubjectSummary {
  id: string;
  name: string;
  code: string;
  description: string | null;
  chapter_count: number;
}

export interface StudentChapterSummary {
  id: string;
  chapter_number: number;
  title: string;
  description: string | null;
  has_available_quiz: boolean;
}

export interface StudentQuizActivity {
  attempt_id: string;
  title: string;
  subject_name: string;
  chapter_title: string;
  score: number;
  total_questions: number;
  percentage: number;
  completed_at: string;
}

export interface StudentSubjectDetail extends StudentSubjectSummary {
  chapters: StudentChapterSummary[];
}

export interface StudentDashboard {
  student_name: string;
  school_name: string;
  enrollment: StudentEnrollmentContext;
  subject_count: number;
  chapter_count: number;
  subjects: StudentSubjectSummary[];
  completed_quiz_count: number;
  recent_activity: StudentQuizActivity[];
}

export interface StudentChapterDetail extends StudentChapterSummary {
  subject_id: string;
  subject_name: string;
  class_name: string;
}
