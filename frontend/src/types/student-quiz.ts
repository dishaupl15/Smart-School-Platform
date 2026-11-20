export interface QuizOption {
  id: string;
  text: string;
}

export interface QuizQuestion {
  attempt_question_id: string;
  display_order: number;
  question_text: string;
  options: QuizOption[];
  selected_option_id: string | null;
  language_code: "en" | "hi" | "mr";
  feedback: {
    is_correct: boolean;
    correct_option_id: string;
    explanation: string | null;
  } | null;
}

export interface QuizAttempt {
  status: "IN_PROGRESS";
  attempt_id: string;
  quiz_title: string;
  started_at: string;
  expires_at: string;
  remaining_seconds: number;
  total_questions: number;
  language_code: "en" | "hi" | "mr";
  questions: QuizQuestion[];
}

export interface QuizResultOption extends QuizOption {
  is_correct: boolean;
}

export interface QuizResultQuestion {
  attempt_question_id: string;
  display_order: number;
  question_text: string;
  options: QuizResultOption[];
  selected_option_id: string | null;
  correct_option_id: string;
  explanation: string | null;
  is_correct: boolean;
  language_code: "en" | "hi" | "mr";
}

export interface QuizResult {
  status: "COMPLETED";
  attempt_id: string;
  quiz_title: string;
  started_at: string;
  completed_at: string;
  total_questions: number;
  correct_answers: number;
  incorrect_answers: number;
  unanswered_questions: number;
  score: number;
  percentage: number;
  time_taken_seconds: number;
  language_code: "en" | "hi" | "mr";
  questions: QuizResultQuestion[];
}

export interface QuizHistoryItem {
  attempt_id: string;
  quiz_title: string;
  subject_id: string;
  subject_name: string;
  chapter_id: string;
  chapter_title: string;
  score: number;
  total_questions: number;
  percentage: number;
  completed_at: string;
}

export interface QuizHistory {
  items: QuizHistoryItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface QuizSubjectPerformance {
  subject_id: string;
  subject_name: string;
  completed_quizzes: number;
  average_percentage: number;
}

export interface QuizChapterPerformance {
  chapter_id: string;
  chapter_title: string;
  subject_id: string;
  subject_name: string;
  completed_quizzes: number;
  average_percentage: number;
}

export interface QuizAnalytics {
  total_completed_quizzes: number;
  total_questions: number;
  total_correct_answers: number;
  average_percentage: number;
  highest_percentage: number;
  recent_activity: QuizHistoryItem[];
  subject_performance: QuizSubjectPerformance[];
  chapter_performance: QuizChapterPerformance[];
  strongest_subjects: QuizSubjectPerformance[];
  needs_improvement_subjects: QuizSubjectPerformance[];
  strongest_chapters: QuizChapterPerformance[];
  needs_improvement_chapters: QuizChapterPerformance[];
}

export interface QuizReady {
  status: "NOT_STARTED";
  quiz_id: string;
  quiz_title: string;
  total_questions: number;
  duration_minutes: number;
}

export type QuizCurrent = QuizReady | QuizAttempt | QuizResult;
