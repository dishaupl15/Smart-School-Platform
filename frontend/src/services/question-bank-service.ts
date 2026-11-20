import { apiDownload, apiRequest } from "@/services/api-client";
import type {
  QuestionDetail,
  QuestionDraft,
  QuestionImportPreview,
  QuestionImportResult,
  QuestionLanguage,
  QuestionListResponse,
  QuestionStats,
  QuestionStatus,
} from "@/types/question-bank";

type QuestionQuery = {
  search?: string;
  class_id?: string;
  subject_id?: string;
  chapter_id?: string;
  difficulty?: string;
  status?: string;
  language?: QuestionLanguage;
  incomplete_translation?: boolean;
  sort_by?: "created_at" | "updated_at" | "difficulty" | "status";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

function queryString(query: QuestionQuery = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const value = params.toString();
  return value ? `?${value}` : "";
}

export const questionBankService = {
  stats: () => apiRequest<QuestionStats>("/admin/question-bank/stats"),
  list: (query: QuestionQuery = {}) =>
    apiRequest<QuestionListResponse>(`/admin/questions${queryString(query)}`),
  get: (id: string) => apiRequest<QuestionDetail>(`/admin/questions/${id}`),
  create: (question: QuestionDraft) =>
    apiRequest<QuestionDetail>("/admin/questions", {
      method: "POST",
      body: JSON.stringify(question),
    }),
  update: (id: string, question: QuestionDraft) =>
    apiRequest<QuestionDetail>(`/admin/questions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(question),
    }),
  duplicate: (id: string) =>
    apiRequest<QuestionDetail>(`/admin/questions/${id}/duplicate`, {
      method: "POST",
    }),
  status: (id: string, status: QuestionStatus) =>
    apiRequest<QuestionDetail>(`/admin/questions/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  archive: (id: string) =>
    apiRequest<QuestionDetail>(`/admin/questions/${id}/archive`, {
      method: "POST",
    }),
  importPreview: (file: File) => {
    const body = new FormData();
    body.set("file", file);
    return apiRequest<QuestionImportPreview>(
      "/admin/questions/import/preview",
      {
        method: "POST",
        body,
      },
    );
  },
  importConfirm: (importId: string, mode: "valid_rows" | "all_or_nothing") =>
    apiRequest<QuestionImportResult>("/admin/questions/import/confirm", {
      method: "POST",
      body: JSON.stringify({ import_id: importId, mode }),
    }),
  importReport: (importId: string) =>
    apiRequest<QuestionImportResult>(
      `/admin/questions/import/report/${importId}`,
    ),
  importReportCsv: (importId: string) =>
    apiDownload(`/admin/questions/imports/${importId}/report/download`),
  importTemplate: () => apiDownload("/admin/questions/import/template"),
};
