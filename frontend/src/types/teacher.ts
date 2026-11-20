export interface TeacherQuizResult {
  attempt_id: string;
  student_id: string;
  student_name: string;
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
  chapter_id: string;
  chapter_title: string;
  quiz_title: string;
  score: number;
  total_questions: number;
  percentage: number;
  completed_at: string;
}

export interface TeacherClass {
  class_id: string;
  class_name: string;
  grade_number: number;
  section: string | null;
  academic_year: string;
  subject_id: string;
  subject_name: string;
  student_count: number;
  completed_quiz_count: number;
  average_percentage: number;
}

export interface TeacherStudent {
  student_id: string;
  full_name: string;
  email: string | null;
  class_id: string;
  class_name: string;
  grade_number: number;
  section: string | null;
  academic_year: string;
  completed_quiz_count: number;
  average_percentage: number;
}

export interface TeacherSubjectPerformance {
  subject_id: string;
  subject_name: string;
  completed_quiz_count: number;
  average_percentage: number;
}

export interface TeacherChapterPerformance {
  chapter_id: string;
  chapter_title: string;
  subject_id: string;
  subject_name: string;
  completed_quiz_count: number;
  average_percentage: number;
}

export interface TeacherDashboard {
  assigned_class_count: number;
  assigned_subject_count: number;
  student_count: number;
  completed_quiz_count: number;
  average_percentage: number;
  recent_results: TeacherQuizResult[];
}

export interface TeacherResultsPage {
  items: TeacherQuizResult[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface TeacherStudentPerformance {
  student_id: string;
  full_name: string;
  class_id: string;
  class_name: string;
  academic_year: string;
  completed_quiz_count: number;
  total_correct_answers: number;
  average_percentage: number;
  subject_performance: TeacherSubjectPerformance[];
  chapter_performance: TeacherChapterPerformance[];
  recent_results: TeacherQuizResult[];
}

export interface TeacherAnalytics {
  student_count: number;
  completed_quiz_count: number;
  average_percentage: number;
  highest_percentage: number;
  subject_performance: TeacherSubjectPerformance[];
  chapter_performance: TeacherChapterPerformance[];
  recent_results: TeacherQuizResult[];
}
