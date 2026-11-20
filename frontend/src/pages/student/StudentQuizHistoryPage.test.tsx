import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderApp } from "@/test/test-utils";
import {
  StudentQuizHistoryPage,
  StudentQuizResultPage,
} from "@/pages/student/StudentQuizHistoryPage";
import type { QuizHistory, QuizResult } from "@/types/student-quiz";

const historyItem = {
  attempt_id: "attempt-1",
  quiz_title: "Numbers quiz",
  subject_id: "subject-1",
  subject_name: "Mathematics",
  chapter_id: "chapter-1",
  chapter_title: "Numbers",
  score: 18,
  total_questions: 20,
  percentage: 90,
  completed_at: "2026-04-06T12:00:00Z",
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderHistory() {
  return renderApp(
    <MemoryRouter initialEntries={["/student/quiz/history"]}>
      <Routes>
        <Route
          path="/student/quiz/history"
          element={<StudentQuizHistoryPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("student quiz history", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("filters history and navigates its paginated results", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/student/subjects")) {
        return response([
          {
            id: "subject-1",
            name: "Mathematics",
            code: "MATH",
            description: null,
            chapter_count: 1,
          },
        ]);
      }
      if (url.endsWith("/student/subjects/subject-1")) {
        return response({
          id: "subject-1",
          name: "Mathematics",
          code: "MATH",
          description: null,
          chapter_count: 1,
          chapters: [
            {
              id: "chapter-1",
              chapter_number: 1,
              title: "Numbers",
              description: null,
              has_available_quiz: true,
            },
          ],
        });
      }
      if (url.includes("/student/quiz/history")) {
        const page = new URL(url).searchParams.get("page");
        const body: QuizHistory = {
          items: page === "2" ? [] : [historyItem],
          page: Number(page),
          page_size: 10,
          total_items: 11,
          total_pages: 2,
        };
        return response(body);
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderHistory();

    expect(await screen.findByText("Numbers quiz")).toBeInTheDocument();
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Filter by subject" }),
      "subject-1",
    );
    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Filter by chapter" }),
      "chapter-1",
    );
    await user.type(screen.getByLabelText("Completed from"), "2026-04-04");
    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("subject_id=subject-1&chapter_id=chapter-1"),
        expect.anything(),
      );
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("date_from=2026-04-04"),
        expect.anything(),
      );
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("page=2"),
        expect.anything(),
      );
    });
    expect(
      await screen.findByText("No completed quizzes found"),
    ).toBeInTheDocument();
  });

  it("renders a saved attempt's detailed result snapshot", async () => {
    const result: QuizResult = {
      status: "COMPLETED",
      attempt_id: "attempt-1",
      quiz_title: "Numbers quiz",
      started_at: "2026-04-06T11:00:00Z",
      completed_at: "2026-04-06T12:00:00Z",
      total_questions: 20,
      correct_answers: 18,
      incorrect_answers: 2,
      unanswered_questions: 0,
      score: 18,
      percentage: 90,
      time_taken_seconds: 3600,
      language_code: "en",
      questions: [
        {
          attempt_question_id: "attempt-question-1",
          display_order: 1,
          question_text: "Saved question text",
          options: [
            {
              id: "option-1",
              text: "Saved correct answer",
              is_correct: true,
            },
          ],
          selected_option_id: "option-1",
          correct_option_id: "option-1",
          explanation: "Saved explanation",
          is_correct: true,
          language_code: "en",
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/student/quiz/attempts/attempt-1/result"))
          return response(result);
        throw new Error(`Unexpected request: ${url}`);
      }),
    );
    renderApp(
      <MemoryRouter initialEntries={["/student/quiz/history/attempt-1"]}>
        <Routes>
          <Route
            path="/student/quiz/history/:attemptId"
            element={<StudentQuizResultPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Numbers quiz" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Saved question text/)).toBeInTheDocument();
    expect(
      screen.getByText("Saved correct answer · Correct answer · Your answer"),
    ).toBeInTheDocument();
    expect(screen.getByText("Saved explanation")).toBeInTheDocument();
  });
});
