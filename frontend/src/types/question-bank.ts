import type { Page } from "@/types/admin";

export type QuestionDifficulty = "EASY" | "MEDIUM" | "HARD";
export type QuestionStatus = "DRAFT" | "REVIEW" | "APPROVED" | "ARCHIVED";
export type QuestionLanguage = "en" | "hi" | "mr";

export interface QuestionTranslation {
  language_code: QuestionLanguage;
  question_text: string;
  explanation: string | null;
}

export interface OptionTranslation {
  language_code: QuestionLanguage;
  option_text: string;
}

export interface QuestionOption {
  id: string;
  option_key: string;
  display_order: number;
  is_correct: boolean;
  translations: OptionTranslation[];
}

export interface QuestionSummary {
  id: string;
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
  chapter_id: string;
  chapter_title: string;
  difficulty: QuestionDifficulty;
  status: QuestionStatus;
  question_type: "SINGLE_CHOICE";
  preview: string;
  languages: QuestionLanguage[];
  option_count: number;
  created_at: string;
  updated_at: string;
}

export interface QuestionDetail extends QuestionSummary {
  translations: QuestionTranslation[];
  options: QuestionOption[];
  created_by: string | null;
  updated_by: string | null;
}

export interface QuestionDraft {
  class_id: string;
  subject_id: string;
  chapter_id: string;
  question_type: "SINGLE_CHOICE";
  difficulty: QuestionDifficulty;
  translations: QuestionTranslation[];
  options: Array<{
    option_key: string;
    display_order: number;
    is_correct: boolean;
    translations: OptionTranslation[];
  }>;
}

export interface QuestionStats {
  total: number;
  draft: number;
  review: number;
  approved: number;
  archived: number;
  by_subject: Array<{
    subject_id: string;
    subject_name: string;
    count: number;
  }>;
  by_chapter: Array<{
    chapter_id: string;
    chapter_title: string;
    count: number;
  }>;
  language_coverage: Array<{ language_code: QuestionLanguage; count: number }>;
}

export type QuestionListResponse = Page<QuestionSummary>;

export interface ImportPreviewRow {
  row_number: number;
  question: string;
  valid: boolean;
  duplicate: boolean;
  errors: string[];
  warnings: string[];
}

export interface QuestionImportPreview {
  import_id: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_rows: number;
  rows: ImportPreviewRow[];
}

export interface QuestionImportResult {
  import_id: string;
  inserted: number;
  rejected: number;
  rows: ImportPreviewRow[];
}
