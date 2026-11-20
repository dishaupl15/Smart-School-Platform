import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { z } from "zod";
import { adminService } from "@/services/admin-service";
import { questionBankService } from "@/services/question-bank-service";
import type {
  QuestionDetail,
  QuestionDraft,
  QuestionLanguage,
  QuestionStatus,
  QuestionTranslation,
} from "@/types/question-bank";

const languages: Array<{ code: QuestionLanguage; name: string }> = [
  { code: "en", name: "English" },
  { code: "hi", name: "Hindi" },
  { code: "mr", name: "Marathi" },
];

const blankTranslations = (): QuestionTranslation[] =>
  languages.map(({ code }) => ({
    language_code: code,
    question_text: "",
    explanation: null,
  }));

const questionSchema = z.object({
  class_id: z.string().min(1, "Select a class."),
  subject_id: z.string().min(1, "Select a subject."),
  chapter_id: z.string().min(1, "Select a chapter."),
  difficulty: z.enum(["EASY", "MEDIUM", "HARD"]),
});

type QuestionFormValues = z.infer<typeof questionSchema>;

function ErrorMessage({ children }: { children: string }) {
  return (
    <p className="admin-error" role="alert">
      {children}
    </p>
  );
}

function StatusBadge({ status }: { status: QuestionStatus }) {
  return <span className={`qb-status ${status.toLowerCase()}`}>{status}</span>;
}

function LanguageCoverage({ available }: { available: QuestionLanguage[] }) {
  return (
    <span className="qb-languages" aria-label="Available translations">
      {languages.map(({ code, name }) => (
        <span
          key={code}
          className={available.includes(code) ? "complete" : "missing"}
          title={`${name}: ${available.includes(code) ? "available" : "missing"}`}
        >
          {code.toUpperCase()}
        </span>
      ))}
    </span>
  );
}

export function QuestionBankDashboardPage() {
  const stats = useQuery({
    queryKey: ["admin", "question-bank", "stats"],
    queryFn: questionBankService.stats,
  });

  if (stats.isLoading)
    return (
      <div className="admin-loading" role="status">
        Loading question bank…
      </div>
    );
  if (stats.isError || !stats.data)
    return (
      <ErrorMessage>
        {stats.error instanceof Error
          ? stats.error.message
          : "Could not load question bank statistics."}
      </ErrorMessage>
    );

  const values: Array<[string, number]> = [
    ["Total questions", stats.data.total],
    ["Draft", stats.data.draft],
    ["In review", stats.data.review],
    ["Approved", stats.data.approved],
    ["Archived", stats.data.archived],
  ];

  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">Learning content</div>
          <h1>Question bank</h1>
          <p>Manage multilingual single-choice questions for your school.</p>
        </div>
      </div>
      <section
        className="admin-stat-grid qb-stat-grid"
        aria-label="Question statistics"
      >
        {values.map(([label, count]) => (
          <Link className="admin-stat-card" to="/admin/questions" key={label}>
            <span className="admin-stat-label">{label}</span>
            <strong>{count.toLocaleString()}</strong>
          </Link>
        ))}
      </section>
      <div className="admin-dashboard-grid">
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Questions by subject</h2>
          </div>
          {stats.data.by_subject.length === 0 ? (
            <p className="admin-empty">No questions yet.</p>
          ) : (
            <ul className="qb-breakdown">
              {stats.data.by_subject.map((item) => (
                <li key={item.subject_id}>
                  <span>{item.subject_name}</span>
                  <strong>{item.count}</strong>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Language coverage</h2>
          </div>
          <ul className="qb-breakdown">
            {languages.map(({ code, name }) => (
              <li key={code}>
                <span>{name}</span>
                <strong>
                  {stats.data.language_coverage.find(
                    (item) => item.language_code === code,
                  )?.count ?? 0}
                </strong>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <h2>Questions by chapter</h2>
        </div>
        {stats.data.by_chapter.length === 0 ? (
          <p className="admin-empty">No chapter questions yet.</p>
        ) : (
          <ul className="qb-breakdown">
            {stats.data.by_chapter.map((item) => (
              <li key={item.chapter_id}>
                <span>{item.chapter_title}</span>
                <strong>{item.count}</strong>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <div>
            <h2>Get started</h2>
            <p>Create, browse, or import questions.</p>
          </div>
        </div>
        <div className="qb-actions">
          <Link className="admin-button primary" to="/admin/questions/new">
            Create question
          </Link>
          <Link className="admin-button secondary" to="/admin/questions/import">
            Import questions
          </Link>
          <Link className="admin-button secondary" to="/admin/questions">
            Browse question bank
          </Link>
          <Link
            className="admin-button secondary"
            to="/admin/questions?status=REVIEW"
          >
            Review pending questions
          </Link>
        </div>
      </section>
    </div>
  );
}

export function QuestionListPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [status, setStatus] = useState(() => searchParams.get("status") ?? "");
  const [language, setLanguage] = useState("");
  const [incompleteOnly, setIncompleteOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const classes = useQuery({
    queryKey: ["admin", "classes", "question-filter"],
    queryFn: () => adminService.classes({ page_size: 100 }),
  });
  const selectedClass = classes.data?.items.find((item) => item.id === classId);
  const subjects = selectedClass?.subjects ?? [];
  const chapters = useQuery({
    queryKey: ["admin", "chapters", classId, subjectId],
    queryFn: () =>
      adminService.chapters({
        class_id: classId,
        subject_id: subjectId,
        page_size: 100,
      }),
    enabled: Boolean(classId && subjectId),
  });
  const results = useQuery({
    queryKey: [
      "admin",
      "questions",
      {
        search,
        classId,
        subjectId,
        chapterId,
        difficulty,
        status,
        language,
        incompleteOnly,
        page,
        sortBy,
        sortOrder,
      },
    ],
    queryFn: () =>
      questionBankService.list({
        search: search || undefined,
        class_id: classId || undefined,
        subject_id: subjectId || undefined,
        chapter_id: chapterId || undefined,
        difficulty: difficulty || undefined,
        status: status || undefined,
        language: (language || undefined) as QuestionLanguage | undefined,
        incomplete_translation: incompleteOnly || undefined,
        page,
        page_size: 20,
        sort_by: sortBy as
          "created_at" | "updated_at" | "difficulty" | "status",
        sort_order: sortOrder as "asc" | "desc",
      }),
  });
  const duplicate = useMutation({
    mutationFn: questionBankService.duplicate,
    onSuccess: (question) => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "questions"] });
      void queryClient.invalidateQueries({
        queryKey: ["admin", "question-bank"],
      });
      navigate(`/admin/questions/${question.id}`);
    },
  });
  const archive = useMutation({
    mutationFn: questionBankService.archive,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "questions"] });
      void queryClient.invalidateQueries({
        queryKey: ["admin", "question-bank"],
      });
    },
  });

  const resetPage = () => setPage(1);
  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">Question bank</div>
          <h1>Browse questions</h1>
          <p>Search and manage reusable school questions.</p>
        </div>
        <div className="qb-actions">
          <Link className="admin-button secondary" to="/admin/questions/import">
            Import
          </Link>
          <Link className="admin-button primary" to="/admin/questions/new">
            Create question
          </Link>
        </div>
      </div>
      <section className="admin-panel">
        <div className="admin-toolbar qb-filters">
          <label className="admin-search">
            Search
            <input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                resetPage();
              }}
              placeholder="Question text"
            />
          </label>
          <label>
            Class
            <select
              value={classId}
              onChange={(event) => {
                setClassId(event.target.value);
                setSubjectId("");
                setChapterId("");
                resetPage();
              }}
            >
              <option value="">All classes</option>
              {classes.data?.items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Subject
            <select
              value={subjectId}
              disabled={!classId}
              onChange={(event) => {
                setSubjectId(event.target.value);
                setChapterId("");
                resetPage();
              }}
            >
              <option value="">All subjects</option>
              {subjects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Chapter
            <select
              value={chapterId}
              disabled={!subjectId}
              onChange={(event) => {
                setChapterId(event.target.value);
                resetPage();
              }}
            >
              <option value="">All chapters</option>
              {chapters.data?.items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.chapter_number}. {item.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Difficulty
            <select
              value={difficulty}
              onChange={(event) => {
                setDifficulty(event.target.value);
                resetPage();
              }}
            >
              <option value="">All levels</option>
              <option>EASY</option>
              <option>MEDIUM</option>
              <option>HARD</option>
            </select>
          </label>
          <label>
            Status
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                resetPage();
              }}
            >
              <option value="">All statuses</option>
              <option>DRAFT</option>
              <option>REVIEW</option>
              <option>APPROVED</option>
              <option>ARCHIVED</option>
            </select>
          </label>
          <label>
            Language
            <select
              value={language}
              onChange={(event) => {
                setLanguage(event.target.value);
                resetPage();
              }}
            >
              <option value="">Any language</option>
              {languages.map(({ code, name }) => (
                <option key={code} value={code}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="qb-checkbox">
            <input
              type="checkbox"
              checked={incompleteOnly}
              onChange={(event) => {
                setIncompleteOnly(event.target.checked);
                resetPage();
              }}
            />
            Incomplete translations
          </label>
          <label>
            Sort
            <select
              value={sortBy}
              onChange={(event) => {
                setSortBy(event.target.value);
                resetPage();
              }}
            >
              <option value="updated_at">Recently updated</option>
              <option value="created_at">Recently created</option>
              <option value="difficulty">Difficulty</option>
              <option value="status">Status</option>
            </select>
          </label>
          <label>
            Order
            <select
              value={sortOrder}
              onChange={(event) => {
                setSortOrder(event.target.value);
                resetPage();
              }}
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </label>
        </div>
        {results.isLoading ? (
          <div className="admin-loading" role="status">
            Loading questions…
          </div>
        ) : results.isError ? (
          <ErrorMessage>{results.error.message}</ErrorMessage>
        ) : results.data?.items.length === 0 ? (
          <p className="admin-empty">No questions match these filters.</p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Question</th>
                  <th>Academic context</th>
                  <th>Difficulty</th>
                  <th>Status</th>
                  <th>Languages</th>
                  <th>Options</th>
                  <th>Created</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.data?.items.map((question) => (
                  <tr key={question.id}>
                    <td>
                      <Link
                        className="admin-text-link"
                        to={`/admin/questions/${question.id}`}
                      >
                        {question.preview || "Untitled question"}
                      </Link>
                    </td>
                    <td>
                      {question.class_name}
                      <small className="table-subtext">
                        {question.subject_name} · {question.chapter_title}
                      </small>
                    </td>
                    <td>{question.difficulty}</td>
                    <td>
                      <StatusBadge status={question.status} />
                    </td>
                    <td>
                      <LanguageCoverage available={question.languages} />
                    </td>
                    <td>{question.option_count}</td>
                    <td>
                      {new Date(question.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      {new Date(question.updated_at).toLocaleDateString()}
                    </td>
                    <td className="qb-row-actions">
                      <Link
                        className="admin-button subtle"
                        to={`/admin/questions/${question.id}`}
                      >
                        Edit
                      </Link>
                      <button
                        className="admin-button subtle"
                        disabled={duplicate.isPending}
                        onClick={() => duplicate.mutate(question.id)}
                      >
                        Duplicate
                      </button>
                      {question.status !== "ARCHIVED" && (
                        <button
                          className="admin-button subtle"
                          disabled={archive.isPending}
                          onClick={() => {
                            if (
                              window.confirm(
                                "Archive this question? It will not be available for future quizzes.",
                              )
                            )
                              archive.mutate(question.id);
                          }}
                        >
                          Archive
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {(duplicate.isError || archive.isError) && (
          <ErrorMessage>
            {(duplicate.error ?? archive.error)?.message ??
              "The action failed."}
          </ErrorMessage>
        )}
        {results.data && (
          <div className="admin-pagination">
            <span>
              {results.data.total.toLocaleString()} questions · Page {page} of{" "}
              {Math.max(results.data.pages, 1)}
            </span>
            <div>
              <button
                className="admin-button secondary"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </button>
              <button
                className="admin-button secondary"
                disabled={page >= results.data.pages}
                onClick={() => setPage(page + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function useAcademicChoices(classId: string, subjectId: string) {
  const classes = useQuery({
    queryKey: ["admin", "classes", "question-form"],
    queryFn: () => adminService.classes({ is_active: true, page_size: 100 }),
  });
  const selectedClass = classes.data?.items.find((item) => item.id === classId);
  const subjects = selectedClass?.subjects ?? [];
  const chapters = useQuery({
    queryKey: ["admin", "chapters", "question-form", classId, subjectId],
    queryFn: () =>
      adminService.chapters({
        class_id: classId,
        subject_id: subjectId,
        is_active: true,
        page_size: 100,
      }),
    enabled: Boolean(classId && subjectId),
  });
  return {
    classes: classes.data?.items ?? [],
    subjects,
    chapters: chapters.data?.items ?? [],
    classesLoading: classes.isLoading,
  };
}

function QuestionEditor({ existing }: { existing?: QuestionDetail }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<QuestionLanguage>("en");
  const [showPreview, setShowPreview] = useState(false);
  const [translations, setTranslations] = useState<QuestionTranslation[]>(
    () => existing?.translations ?? blankTranslations(),
  );
  const [optionTexts, setOptionTexts] = useState<
    Record<string, Record<QuestionLanguage, string>>
  >(() => {
    const result: Record<string, Record<QuestionLanguage, string>> = {};
    for (const key of ["A", "B", "C", "D"]) {
      result[key] = { en: "", hi: "", mr: "" };
      for (const option of existing?.options ?? []) {
        if (option.option_key === key)
          for (const translation of option.translations)
            result[key][translation.language_code] = translation.option_text;
      }
    }
    return result;
  });
  const [optionOrder, setOptionOrder] = useState<string[]>(() => {
    const stored =
      existing?.options
        .slice()
        .sort((left, right) => left.display_order - right.display_order)
        .map((option) => option.option_key)
        .filter((key) => ["A", "B", "C", "D"].includes(key)) ?? [];
    return [
      ...stored,
      ...["A", "B", "C", "D"].filter((key) => !stored.includes(key)),
    ];
  });
  const initialCorrect =
    existing?.options.find((option) => option.is_correct)?.option_key ?? "";
  const [correctKey, setCorrectKey] = useState(initialCorrect);
  const form = useForm<QuestionFormValues>({
    resolver: zodResolver(questionSchema),
    defaultValues: {
      class_id: existing?.class_id ?? "",
      subject_id: existing?.subject_id ?? "",
      chapter_id: existing?.chapter_id ?? "",
      difficulty: existing?.difficulty ?? "MEDIUM",
    },
  });
  const classId = form.watch("class_id");
  const subjectId = form.watch("subject_id");
  const choices = useAcademicChoices(classId, subjectId);
  const save = useMutation({
    mutationFn: (body: QuestionDraft) =>
      existing
        ? questionBankService.update(existing.id, body)
        : questionBankService.create(body),
    onSuccess: (question) => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "questions"] });
      void queryClient.invalidateQueries({
        queryKey: ["admin", "question-bank"],
      });
      navigate(`/admin/questions/${question.id}`);
    },
  });
  const statusChange = useMutation({
    mutationFn: (status: QuestionStatus) =>
      questionBankService.status(existing!.id, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "questions"] });
      void queryClient.invalidateQueries({
        queryKey: ["admin", "question-bank"],
      });
      void queryClient.invalidateQueries({
        queryKey: ["admin", "question", existing!.id],
      });
    },
  });

  const setTranslation = (
    language: QuestionLanguage,
    field: "question_text" | "explanation",
    value: string,
  ) => {
    setTranslations((current) =>
      current.map((item) =>
        item.language_code === language ? { ...item, [field]: value } : item,
      ),
    );
  };
  const updateOption = (
    key: string,
    language: QuestionLanguage,
    value: string,
  ) => {
    setOptionTexts((current) => ({
      ...current,
      [key]: { ...current[key], [language]: value },
    }));
  };
  const buildBody = (values: QuestionFormValues): QuestionDraft => ({
    ...values,
    question_type: "SINGLE_CHOICE",
    translations: translations
      .filter((item) => item.question_text.trim())
      .map((item) => ({
        ...item,
        question_text: item.question_text.trim(),
        explanation: item.explanation?.trim() || null,
      })),
    options: optionOrder.map((key, index) => ({
      option_key: key,
      display_order: index + 1,
      is_correct: key === correctKey,
      translations: languages
        .filter(({ code }) => optionTexts[key][code].trim())
        .map(({ code }) => ({
          language_code: code,
          option_text: optionTexts[key][code].trim(),
        })),
    })),
  });
  const submit = form.handleSubmit((values) => {
    if (
      existing?.status === "APPROVED" &&
      !window.confirm(
        "This question is approved. Saving changes updates its current bank content, but not any historical attempt snapshots. Continue?",
      )
    ) {
      return;
    }
    if (!translations.some((item) => item.question_text.trim())) {
      form.setError("root", {
        message: "Enter question text in at least one language before saving.",
      });
      return;
    }
    if (!correctKey) {
      form.setError("root", {
        message: "Select exactly one correct answer before saving.",
      });
      return;
    }
    if (
      existing &&
      (existing.translations.some(
        (translation) =>
          !translations
            .find((item) => item.language_code === translation.language_code)
            ?.question_text.trim(),
      ) ||
        existing.options.some((option) =>
          option.translations.some(
            (translation) =>
              !optionTexts[option.option_key]?.[
                translation.language_code
              ]?.trim(),
          ),
        )) &&
      !window.confirm(
        "One or more saved question or option translations are blank and will be removed. Continue?",
      )
    ) {
      return;
    }
    save.mutate(buildBody(values));
  });
  const selectedTranslation = translations.find(
    (item) => item.language_code === tab,
  )!;
  const selectedClass = choices.classes.find((item) => item.id === classId);

  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">Question bank</div>
          <h1>{existing ? "Edit question" : "Create question"}</h1>
          <p>
            Single-choice MCQ · Draft until you deliberately submit for review.
          </p>
        </div>
        <button
          type="button"
          className="admin-button secondary"
          onClick={() => setShowPreview((value) => !value)}
        >
          {showPreview ? "Close preview" : "Preview"}
        </button>
      </div>
      <form className="qb-editor" onSubmit={(event) => void submit(event)}>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>1. Academic context</h2>
          </div>
          <div className="admin-form-grid compact">
            <label>
              Class
              <select
                {...form.register("class_id", {
                  onChange: () => {
                    form.setValue("subject_id", "");
                    form.setValue("chapter_id", "");
                  },
                })}
              >
                <option value="">Select class</option>
                {choices.classes.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              {form.formState.errors.class_id && (
                <small className="field-error">
                  {form.formState.errors.class_id.message}
                </small>
              )}
            </label>
            <label>
              Subject
              <select
                {...form.register("subject_id", {
                  onChange: () => form.setValue("chapter_id", ""),
                })}
                disabled={!classId}
              >
                <option value="">Select subject</option>
                {choices.subjects.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              {form.formState.errors.subject_id && (
                <small className="field-error">
                  {form.formState.errors.subject_id.message}
                </small>
              )}
            </label>
            <label>
              Chapter
              <select {...form.register("chapter_id")} disabled={!subjectId}>
                <option value="">Select chapter</option>
                {choices.chapters.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.chapter_number}. {item.title}
                  </option>
                ))}
              </select>
              {form.formState.errors.chapter_id && (
                <small className="field-error">
                  {form.formState.errors.chapter_id.message}
                </small>
              )}
            </label>
          </div>
          {choices.classesLoading && (
            <div className="admin-loading">Loading academic context…</div>
          )}
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>2. Question configuration</h2>
          </div>
          <div className="admin-form-grid compact">
            <label>
              Question type
              <input value="Single choice" readOnly />
            </label>
            <label>
              Difficulty
              <select {...form.register("difficulty")}>
                <option value="EASY">Easy</option>
                <option value="MEDIUM">Medium</option>
                <option value="HARD">Hard</option>
              </select>
            </label>
            <label>
              Status
              <input value={existing?.status ?? "DRAFT"} readOnly />
            </label>
          </div>
          {existing && (
            <div className="qb-record-meta">
              <span>
                <strong>Class:</strong> {existing.class_name}
              </span>
              <span>
                <strong>Subject:</strong> {existing.subject_name}
              </span>
              <span>
                <strong>Chapter:</strong> {existing.chapter_title}
              </span>
              <span>
                <strong>Created:</strong>{" "}
                {new Date(existing.created_at).toLocaleString()}
              </span>
              <span>
                <strong>Updated:</strong>{" "}
                {new Date(existing.updated_at).toLocaleString()}
              </span>
            </div>
          )}
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <div>
              <h2>3. Question content</h2>
              <p>
                Enter translations separately. Missing languages are allowed for
                drafts.
              </p>
            </div>
          </div>
          <div
            className="qb-tabs"
            role="tablist"
            aria-label="Question language"
          >
            {languages.map(({ code, name }) => (
              <button
                type="button"
                role="tab"
                aria-selected={tab === code}
                className={tab === code ? "selected" : ""}
                key={code}
                onClick={() => setTab(code)}
              >
                {name}
                <span>
                  {translations
                    .find((item) => item.language_code === code)
                    ?.question_text.trim()
                    ? "Complete"
                    : "Missing"}
                </span>
              </button>
            ))}
          </div>
          <label className="qb-field">
            Question text ({tab.toUpperCase()})
            <textarea
              maxLength={5000}
              rows={4}
              value={selectedTranslation.question_text}
              onChange={(event) =>
                setTranslation(tab, "question_text", event.target.value)
              }
              placeholder="Enter question text"
            />
          </label>
          <label className="qb-field">
            Explanation ({tab.toUpperCase()}, optional)
            <textarea
              maxLength={2000}
              rows={2}
              value={selectedTranslation.explanation ?? ""}
              onChange={(event) =>
                setTranslation(tab, "explanation", event.target.value)
              }
              placeholder="Explain why the answer is correct"
            />
          </label>
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <div>
              <h2>4. Answer options</h2>
              <p>
                Four options are required; select exactly one correct answer and
                change display order as needed.
              </p>
            </div>
          </div>
          <div className="qb-options">
            {optionOrder.map((key, index) => (
              <div
                className={`qb-option ${correctKey === key ? "correct" : ""}`}
                key={key}
              >
                <label className="qb-correct">
                  <input
                    type="radio"
                    name="correct-option"
                    value={key}
                    checked={correctKey === key}
                    onChange={() => setCorrectKey(key)}
                  />
                  Option {key}
                  {correctKey === key && <strong>Correct answer</strong>}
                </label>
                <div className="qb-language-fields">
                  {languages.map(({ code, name }) => (
                    <label key={code}>
                      {name}
                      <input
                        maxLength={1000}
                        value={optionTexts[key][code]}
                        onChange={(event) =>
                          updateOption(key, code, event.target.value)
                        }
                      />
                    </label>
                  ))}
                </div>
                <small>Display order: {index + 1}</small>
                <div className="qb-order-actions">
                  <button
                    type="button"
                    className="admin-button subtle"
                    disabled={index === 0}
                    onClick={() =>
                      setOptionOrder((current) => {
                        const next = [...current];
                        [next[index - 1], next[index]] = [
                          next[index],
                          next[index - 1],
                        ];
                        return next;
                      })
                    }
                  >
                    Move up
                  </button>
                  <button
                    type="button"
                    className="admin-button subtle"
                    disabled={index === optionOrder.length - 1}
                    onClick={() =>
                      setOptionOrder((current) => {
                        const next = [...current];
                        [next[index], next[index + 1]] = [
                          next[index + 1],
                          next[index],
                        ];
                        return next;
                      })
                    }
                  >
                    Move down
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
        {showPreview && (
          <section
            className="admin-panel qb-preview"
            aria-label={`${tab.toUpperCase()} question preview`}
          >
            <div className="admin-panel-heading">
              <h2>
                5. Preview · {languages.find((item) => item.code === tab)?.name}
              </h2>
            </div>
            <p>
              {selectedTranslation.question_text ||
                "Question text will appear here."}
            </p>
            <ol type="A">
              {optionOrder.map((key) => (
                <li className={key === correctKey ? "correct" : ""} key={key}>
                  {optionTexts[key][tab] || "Option translation missing"}
                  {key === correctKey && <strong> Correct</strong>}
                </li>
              ))}
            </ol>
            {selectedTranslation.explanation && (
              <p className="qb-explanation">
                <strong>Explanation: </strong>
                {selectedTranslation.explanation}
              </p>
            )}
            <small>
              Admin preview only — answer key is not available to student APIs.
            </small>
          </section>
        )}
        {form.formState.errors.root && (
          <ErrorMessage>
            {form.formState.errors.root.message ?? "Question is incomplete."}
          </ErrorMessage>
        )}
        {save.isError && <ErrorMessage>{save.error.message}</ErrorMessage>}
        {statusChange.isError && (
          <ErrorMessage>{statusChange.error.message}</ErrorMessage>
        )}
        <div className="qb-sticky-actions">
          <button
            className="admin-button primary"
            disabled={save.isPending || choices.classesLoading}
          >
            {save.isPending ? "Saving…" : "Save draft"}
          </button>
          {existing?.status === "DRAFT" && (
            <button
              type="button"
              className="admin-button secondary"
              disabled={statusChange.isPending}
              onClick={() => {
                if (window.confirm("Submit this question for review?"))
                  statusChange.mutate("REVIEW");
              }}
            >
              Submit for review
            </button>
          )}
          {existing?.status === "REVIEW" && (
            <button
              type="button"
              className="admin-button primary"
              disabled={statusChange.isPending}
              onClick={() => {
                if (
                  window.confirm(
                    "Approve this question for future quiz use? Ensure all required translations and four options are complete.",
                  )
                )
                  statusChange.mutate("APPROVED");
              }}
            >
              Approve
            </button>
          )}
          {existing?.status === "APPROVED" && (
            <button
              type="button"
              className="admin-button secondary"
              disabled={statusChange.isPending}
              onClick={() => {
                if (
                  window.confirm(
                    "Move this approved question back to draft? It will no longer be eligible for future quizzes until approved again.",
                  )
                )
                  statusChange.mutate("DRAFT");
              }}
            >
              Move to draft before editing
            </button>
          )}
          {existing && existing.status !== "ARCHIVED" && (
            <button
              type="button"
              className="admin-button subtle"
              disabled={statusChange.isPending}
              onClick={() => {
                if (
                  window.confirm(
                    "Archive this question? It will be unavailable for future quiz selection.",
                  )
                )
                  statusChange.mutate("ARCHIVED");
              }}
            >
              Archive
            </button>
          )}
          {existing?.status === "ARCHIVED" && (
            <button
              type="button"
              className="admin-button secondary"
              disabled={statusChange.isPending}
              onClick={() => statusChange.mutate("DRAFT")}
            >
              Restore as draft
            </button>
          )}
        </div>
      </form>
      {selectedClass && (
        <p className="qb-context-note">School class: {selectedClass.name}</p>
      )}
    </div>
  );
}

export function QuestionCreatePage() {
  return <QuestionEditor />;
}

export function QuestionDetailPage() {
  const { id = "" } = useParams();
  const query = useQuery({
    queryKey: ["admin", "question", id],
    queryFn: () => questionBankService.get(id),
    enabled: Boolean(id),
  });
  if (query.isLoading)
    return (
      <div className="admin-loading" role="status">
        Loading question…
      </div>
    );
  if (query.isError || !query.data)
    return (
      <ErrorMessage>
        {query.error?.message ?? "Question not found."}
      </ErrorMessage>
    );
  return <QuestionEditor key={query.data.id} existing={query.data} />;
}

function downloadedFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function QuestionImportPage() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"valid_rows" | "all_or_nothing">(
    "valid_rows",
  );
  const [previewId, setPreviewId] = useState("");
  const preview = useMutation({
    mutationFn: questionBankService.importPreview,
    onSuccess: (data) => setPreviewId(data.import_id),
  });
  const confirm = useMutation({
    mutationFn: () => questionBankService.importConfirm(previewId, mode),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "questions"] });
      void queryClient.invalidateQueries({
        queryKey: ["admin", "question-bank"],
      });
    },
  });
  const report = useMutation({
    mutationFn: (importId: string) =>
      questionBankService.importReportCsv(importId),
    onSuccess: (blob) => downloadedFile(blob, "question-import-report.csv"),
  });
  const downloadTemplate = useMutation({
    mutationFn: questionBankService.importTemplate,
    onSuccess: (blob) => downloadedFile(blob, "question-bank-template.csv"),
  });

  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">Question bank</div>
          <h1>Import questions</h1>
          <p>
            Upload an Excel or CSV file. Preview validation before any questions
            are saved.
          </p>
        </div>
        <button
          className="admin-button secondary"
          disabled={downloadTemplate.isPending}
          onClick={() => downloadTemplate.mutate()}
        >
          Download CSV template
        </button>
      </div>
      {downloadTemplate.isError && (
        <ErrorMessage>{downloadTemplate.error.message}</ErrorMessage>
      )}
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <h2>1. Upload file</h2>
          <p>
            Supported formats: .csv and .xlsx. Macro-enabled files are not
            supported.
          </p>
        </div>
        <form
          className="qb-upload"
          onSubmit={(event) => {
            event.preventDefault();
            if (file) {
              setPreviewId("");
              confirm.reset();
              preview.mutate(file);
            }
          }}
        >
          <label>
            Question file
            <input
              type="file"
              accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          {file && (
            <span>
              {file.name} · {(file.size / 1024).toFixed(1)} KB
            </span>
          )}
          <button
            className="admin-button primary"
            disabled={!file || preview.isPending}
          >
            {preview.isPending ? "Validating…" : "Validate and preview"}
          </button>
        </form>
        {preview.isError && (
          <ErrorMessage>{preview.error.message}</ErrorMessage>
        )}
      </section>
      {preview.data && (
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <div>
              <h2>2. Review import</h2>
              <p>
                No question records have been written yet. Choose whether to
                import valid rows only or require an all-valid file.
              </p>
            </div>
          </div>
          <div className="qb-import-summary">
            <strong>{preview.data.total_rows}</strong> rows ·{" "}
            <strong>{preview.data.valid_rows}</strong> valid ·{" "}
            <strong>{preview.data.invalid_rows}</strong> invalid ·{" "}
            <strong>{preview.data.duplicate_rows}</strong> duplicates
          </div>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Question</th>
                  <th>Result</th>
                  <th>Issues</th>
                </tr>
              </thead>
              <tbody>
                {preview.data.rows.map((row) => (
                  <tr key={row.row_number}>
                    <td>{row.row_number}</td>
                    <td>{row.question || "—"}</td>
                    <td>
                      {row.duplicate
                        ? "Duplicate"
                        : row.valid
                          ? "Valid"
                          : "Invalid"}
                    </td>
                    <td>
                      {[...row.errors, ...row.warnings].join("; ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="qb-import-confirm">
            <label>
              Import policy
              <select
                value={mode}
                onChange={(event) => setMode(event.target.value as typeof mode)}
              >
                <option value="valid_rows">
                  Import valid rows only; reject invalid and duplicate rows
                </option>
                <option value="all_or_nothing">
                  All or nothing; block if any row is invalid or duplicate
                </option>
              </select>
            </label>
            <button
              className="admin-button primary"
              disabled={
                confirm.isPending ||
                preview.data.valid_rows === 0 ||
                (mode === "all_or_nothing" &&
                  (preview.data.invalid_rows > 0 ||
                    preview.data.duplicate_rows > 0))
              }
              onClick={() => confirm.mutate()}
            >
              {confirm.isPending ? "Importing…" : "Confirm import"}
            </button>
          </div>
          {confirm.isError && (
            <ErrorMessage>{confirm.error.message}</ErrorMessage>
          )}
        </section>
      )}
      {confirm.data && (
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>3. Import report</h2>
          </div>
          <p className="qb-success" role="status">
            Imported {confirm.data.inserted} question(s).{" "}
            {confirm.data.rejected} row(s) were rejected.
          </p>
          {confirm.data.rejected > 0 && (
            <button
              className="admin-button secondary"
              disabled={report.isPending}
              onClick={() => report.mutate(confirm.data!.import_id)}
            >
              {report.isPending
                ? "Preparing report…"
                : "Download rejected-row report"}
            </button>
          )}
          {report.isError && (
            <ErrorMessage>{report.error.message}</ErrorMessage>
          )}
        </section>
      )}
    </div>
  );
}
