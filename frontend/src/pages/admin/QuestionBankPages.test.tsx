import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import {
  QuestionBankDashboardPage,
  QuestionCreatePage,
  QuestionDetailPage,
  QuestionImportPage,
  QuestionListPage,
} from "@/pages/admin/QuestionBankPages";
import { renderApp } from "@/test/test-utils";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const page = (items: unknown[] = []) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 20,
  pages: items.length ? 1 : 0,
});

describe("question bank pages", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders database statistics and language coverage", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          total: 25,
          draft: 12,
          review: 4,
          approved: 8,
          archived: 1,
          by_subject: [
            { subject_id: "s1", subject_name: "Science", count: 25 },
          ],
          by_chapter: [],
          language_coverage: [
            { language_code: "en", count: 25 },
            { language_code: "hi", count: 20 },
            { language_code: "mr", count: 18 },
          ],
        }),
      ),
    );
    renderApp(
      <MemoryRouter>
        <QuestionBankDashboardPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Total questions")).toBeInTheDocument();
    expect(screen.getAllByText("25").length).toBeGreaterThan(0);
    expect(screen.getByText("Science")).toBeInTheDocument();
    expect(screen.getByText("Language coverage")).toBeInTheDocument();
  });

  it("searches and paginates on the server", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/admin/questions?") && url.includes("search=force")) {
        return jsonResponse({
          items: [
            {
              id: "q1",
              class_id: "c1",
              class_name: "Grade 8",
              subject_id: "s1",
              subject_name: "Science",
              chapter_id: "ch1",
              chapter_title: "Motion",
              difficulty: "EASY",
              status: "DRAFT",
              question_type: "SINGLE_CHOICE",
              preview: "What is force?",
              languages: ["en"],
              option_count: 4,
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-01T00:00:00Z",
            },
          ],
          total: 21,
          page: 1,
          page_size: 20,
          pages: 2,
        });
      }
      return jsonResponse(page());
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp(
      <MemoryRouter>
        <QuestionListPage />
      </MemoryRouter>,
    );
    await user.type(
      await screen.findByPlaceholderText("Question text"),
      "force",
    );
    expect(await screen.findByText("What is force?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input]) =>
            String(input).includes("page=2") &&
            String(input).includes("search=force"),
        ),
      ).toBe(true),
    );
  });

  it("creates a draft after validation with an explicit correct answer", async () => {
    const user = userEvent.setup();
    let submittedBody: Record<string, unknown> | undefined;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/admin/classes")) {
          return jsonResponse({
            items: [
              {
                id: "class-1",
                name: "Grade 8",
                grade_number: 8,
                academic_year: "2026-27",
                section: null,
                is_active: true,
                student_count: 0,
                subjects: [
                  {
                    id: "subject-1",
                    name: "Science",
                    code: "SCI",
                    is_active: true,
                  },
                ],
                created_at: "2026-01-01T00:00:00Z",
              },
            ],
            total: 1,
            page: 1,
            page_size: 100,
            pages: 1,
          });
        }
        if (url.includes("/admin/chapters")) {
          return jsonResponse({
            items: [{ id: "chapter-1", chapter_number: 1, title: "Motion" }],
            total: 1,
            page: 1,
            page_size: 100,
            pages: 1,
          });
        }
        if (url.endsWith("/admin/questions") && init?.method === "POST") {
          submittedBody = JSON.parse(String(init.body)) as Record<
            string,
            unknown
          >;
          return jsonResponse({ id: "question-1" }, 201);
        }
        return jsonResponse(page());
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderApp(
      <MemoryRouter>
        <QuestionCreatePage />
      </MemoryRouter>,
    );

    await screen.findByRole("option", { name: "Grade 8" });
    await user.selectOptions(await screen.findByLabelText("Class"), "class-1");
    await user.selectOptions(
      await screen.findByLabelText("Subject"),
      "subject-1",
    );
    await user.selectOptions(
      await screen.findByLabelText("Chapter"),
      "chapter-1",
    );
    await user.type(
      screen.getByLabelText("Question text (EN)"),
      "What is motion?",
    );
    await user.click(screen.getByRole("tab", { name: /Hindi/ }));
    await user.type(screen.getByLabelText("Question text (HI)"), "गति क्या है?");
    expect(screen.getByRole("tab", { name: /Hindi/ })).toHaveTextContent(
      "Complete",
    );
    await user.click(screen.getByRole("tab", { name: /English/ }));
    await user.click(screen.getByRole("radio", { name: /Option C/ }));
    await user.click(screen.getByRole("button", { name: "Preview" }));
    expect(
      await screen.findByLabelText("EN question preview"),
    ).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Move down" })[0]);
    await user.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() => expect(submittedBody).toBeDefined());
    expect(submittedBody?.status).toBeUndefined();
    expect(submittedBody?.question_type).toBe("SINGLE_CHOICE");
    const options = submittedBody?.options as Array<{
      option_key: string;
      is_correct: boolean;
      display_order: number;
    }>;
    expect(options).toHaveLength(4);
    expect(
      options
        .filter((option) => option.is_correct)
        .map((option) => option.option_key),
    ).toEqual(["C"]);
    expect(
      (submittedBody?.translations as Array<{ language_code: string }>).map(
        (translation) => translation.language_code,
      ),
    ).toEqual(["en", "hi"]);
    expect(options.slice(0, 2).map((option) => option.option_key)).toEqual([
      "B",
      "A",
    ]);
  });

  it("previews an uploaded file before importing and then confirms it", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/admin/questions/import/preview")) {
          return jsonResponse({
            import_id: "import-1",
            total_rows: 1,
            valid_rows: 1,
            invalid_rows: 0,
            duplicate_rows: 0,
            rows: [
              {
                row_number: 2,
                question: "What is motion?",
                valid: true,
                duplicate: false,
                errors: [],
                warnings: [],
              },
            ],
          });
        }
        if (url.endsWith("/admin/questions/import/confirm")) {
          expect(JSON.parse(String(init?.body))).toEqual({
            import_id: "import-1",
            mode: "valid_rows",
          });
          return jsonResponse({
            import_id: "import-1",
            inserted: 1,
            rejected: 0,
            rows: [],
          });
        }
        return jsonResponse({});
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderApp(
      <MemoryRouter>
        <QuestionImportPage />
      </MemoryRouter>,
    );
    const upload = await screen.findByLabelText("Question file");
    const file = new File(["question_en\nWhat is motion?"], "questions.csv", {
      type: "text/csv",
    });
    await user.upload(upload, file);
    await user.click(
      screen.getByRole("button", { name: "Validate and preview" }),
    );

    expect(await screen.findByText("Valid")).toBeInTheDocument();
    expect(
      screen.getByText(/No question records have been written yet/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm import" }));
    expect(await screen.findByText(/Imported 1 question/)).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith("/admin/questions/import/confirm"),
      ),
    ).toBe(true);
  });

  it("submits a draft for review only after confirmation", async () => {
    const user = userEvent.setup();
    const question = {
      id: "question-1",
      class_id: "class-1",
      class_name: "Grade 8",
      subject_id: "subject-1",
      subject_name: "Science",
      chapter_id: "chapter-1",
      chapter_title: "Motion",
      difficulty: "MEDIUM",
      status: "DRAFT",
      question_type: "SINGLE_CHOICE",
      preview: "What is motion?",
      languages: ["en"],
      option_count: 4,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      translations: [
        {
          language_code: "en",
          question_text: "What is motion?",
          explanation: null,
        },
      ],
      options: ["A", "B", "C", "D"].map((option_key, index) => ({
        id: `option-${option_key}`,
        option_key,
        display_order: index + 1,
        is_correct: option_key === "A",
        translations: [
          { language_code: "en", option_text: `Option ${option_key}` },
        ],
      })),
      created_by: "admin-1",
      updated_by: "admin-1",
    };
    let currentStatus = "DRAFT";
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/admin/questions/question-1/status")) {
          expect(JSON.parse(String(init?.body))).toEqual({ status: "REVIEW" });
          currentStatus = "REVIEW";
          return jsonResponse({ ...question, status: currentStatus });
        }
        if (url.endsWith("/admin/questions/question-1")) {
          return jsonResponse({ ...question, status: currentStatus });
        }
        return jsonResponse(page());
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderApp(
      <MemoryRouter initialEntries={["/admin/questions/question-1"]}>
        <Routes>
          <Route path="/admin/questions/:id" element={<QuestionDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Submit for review" }),
    );
    expect(
      await screen.findByRole("button", { name: "Approve" }),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith("/admin/questions/question-1/status"),
      ),
    ).toBe(true);
  });

  it("archives a question only after confirmation", async () => {
    const user = userEvent.setup();
    const question = {
      id: "question-1",
      class_id: "class-1",
      class_name: "Grade 8",
      subject_id: "subject-1",
      subject_name: "Science",
      chapter_id: "chapter-1",
      chapter_title: "Motion",
      difficulty: "MEDIUM",
      status: "APPROVED",
      question_type: "SINGLE_CHOICE",
      preview: "What is motion?",
      languages: ["en", "hi", "mr"],
      option_count: 4,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/admin/questions?")) {
        return jsonResponse({
          items: [question],
          total: 1,
          page: 1,
          page_size: 20,
          pages: 1,
        });
      }
      if (String(input).includes("/admin/questions/question-1/archive")) {
        return jsonResponse({ ...question, status: "ARCHIVED" });
      }
      return jsonResponse(page());
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderApp(
      <MemoryRouter>
        <QuestionListPage />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: "Archive" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).includes("/admin/questions/question-1/archive"),
        ),
      ).toBe(true);
    });
  });
});
