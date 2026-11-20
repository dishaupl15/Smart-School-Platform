import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { StudentQuizPage } from "@/pages/student/StudentQuizPage";
import { renderApp } from "@/test/test-utils";
import type {
  QuizAttempt,
  QuizQuestion,
  QuizResult,
} from "@/types/student-quiz";

const attemptId = "00000000-0000-4000-8000-000000000001";

function activeAttempt(
  answers: Map<number, string> = new Map(),
  languageCode: "en" | "hi" | "mr" = "en",
): QuizAttempt {
  return {
    status: "IN_PROGRESS",
    attempt_id: attemptId,
    quiz_title: "Numbers quiz",
    started_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 20 * 60_000).toISOString(),
    remaining_seconds: 1200,
    total_questions: 15,
    language_code: languageCode,
    questions: Array.from({ length: 15 }, (_, index): QuizQuestion => {
      const selectedOptionId = answers.get(index + 1) ?? null;
      return {
        attempt_question_id: `question-${index + 1}`,
        display_order: index + 1,
        question_text: `Question ${index + 1}`,
        options: [
          { id: `option-${index + 1}-a`, text: `Option A for ${index + 1}` },
          { id: `option-${index + 1}-b`, text: `Option B for ${index + 1}` },
          { id: `option-${index + 1}-c`, text: `Option C for ${index + 1}` },
          { id: `option-${index + 1}-d`, text: `Option D for ${index + 1}` },
        ],
        selected_option_id: selectedOptionId,
        language_code: languageCode,
        feedback: selectedOptionId
          ? {
              is_correct: selectedOptionId === `option-${index + 1}-b`,
              correct_option_id: `option-${index + 1}-b`,
              explanation: "This is the explanation.",
            }
          : null,
      };
    }),
  };
}

function completedQuiz(): QuizResult {
  return {
    status: "COMPLETED",
    attempt_id: attemptId,
    quiz_title: "Numbers quiz",
    started_at: new Date(Date.now() - 60_000).toISOString(),
    completed_at: new Date().toISOString(),
    total_questions: 15,
    correct_answers: 14,
    incorrect_answers: 1,
    unanswered_questions: 0,
    score: 14,
    percentage: 93.33,
    time_taken_seconds: 45,
    language_code: "hi",
    questions: [
      {
        attempt_question_id: "question-1",
        display_order: 1,
        question_text: "Question 1",
        options: [
          {
            id: "option-1-a",
            text: "Option A for 1",
            is_correct: false,
          },
          {
            id: "option-1-b",
            text: "Option B for 1",
            is_correct: true,
          },
        ],
        selected_option_id: "option-1-a",
        correct_option_id: "option-1-b",
        explanation: "This is the explanation.",
        is_correct: false,
        language_code: "hi",
      },
    ],
  };
}

function response(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function renderQuiz() {
  return renderApp(
    <MemoryRouter initialEntries={["/student/chapters/chapter-1/quiz"]}>
      <Routes>
        <Route
          path="/student/chapters/:chapterId/quiz"
          element={<StudentQuizPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("student quiz", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses the chosen language and gives locked, immediate feedback through completion", async () => {
    const user = userEvent.setup();
    const answers = new Map<number, string>();
    let selectedLanguage = "en";
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/quiz/current")) {
          return response({
            status: "NOT_STARTED",
            quiz_id: "quiz-1",
            quiz_title: "Numbers quiz",
            total_questions: 15,
            duration_minutes: 20,
          });
        }
        if (url.endsWith("/quiz/start")) {
          selectedLanguage = (
            JSON.parse(String(init?.body)) as { language_code: string }
          ).language_code;
          answers.clear();
          return response(activeAttempt(answers, "hi"));
        }
        if (url.includes("/answers/")) {
          const questionNumber = Number(url.match(/question-(\d+)/)?.[1]);
          const answer = JSON.parse(String(init?.body)) as {
            selected_option_id: string;
          };
          answers.set(questionNumber, answer.selected_option_id);
          return response(activeAttempt(answers, "hi"));
        }
        if (url.endsWith("/submit")) return response(completedQuiz());
        throw new Error(`Unexpected API request: ${init?.method} ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderQuiz();

    expect(await screen.findByText(/exactly 15 questions/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Quiz language"), "hi");
    await user.click(screen.getByRole("button", { name: "Begin quiz" }));
    expect(await screen.findByText("Question 1 of 15")).toBeInTheDocument();
    expect(screen.getByText("Language used: HI")).toBeInTheDocument();
    expect(selectedLanguage).toBe("hi");

    await user.click(screen.getByRole("button", { name: /Option A for 1/ }));
    expect(await screen.findByText("Incorrect")).toBeInTheDocument();
    expect(screen.getByText(/Correct answer: Option B for 1/)).toBeInTheDocument();
    expect(screen.getByText("This is the explanation.")).toBeInTheDocument();
    const questionOneAnswer = screen.getByRole("button", {
      name: /Option A for 1/,
    });
    expect(questionOneAnswer).toBeDisabled();
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/answers/")),
    ).toHaveLength(1);

    for (let questionNumber = 1; questionNumber < 15; questionNumber += 1) {
      await user.click(
        screen.getByRole("button", {
          name: `Next Question`,
        }),
      );
      await user.click(
        screen.getByRole("button", {
          name: new RegExp(`Option B for ${questionNumber + 1}`),
        }),
      );
      expect(await screen.findByText("Correct!")).toBeInTheDocument();
    }
    await user.click(screen.getByRole("button", { name: "Finish Quiz" }));

    expect(
      await screen.findByRole("heading", { name: "Numbers quiz" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Quiz results")).toBeInTheDocument();
    expect(screen.getByText("Time taken: 00:45")).toBeInTheDocument();
    expect(screen.getByText("This is the explanation.")).toBeInTheDocument();
    expect(screen.getByText(/14 out of 15/)).toBeInTheDocument();
  });

  it("resumes a saved attempt at the first unanswered question", async () => {
    const answers = new Map([[1, "option-1-b"]]);
    vi.stubGlobal("fetch", vi.fn(async () => response(activeAttempt(answers))));
    renderQuiz();

    expect(await screen.findByText("Question 2 of 15")).toBeInTheDocument();
    expect(screen.getByText("1 of 15 answered")).toBeInTheDocument();
  });
});
