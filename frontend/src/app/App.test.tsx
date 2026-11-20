import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "@/app/App";
import { renderApp } from "@/test/test-utils";
import type { AuthenticatedUser, TokenResponse } from "@/types/auth";

const authenticatedUser: AuthenticatedUser = {
  id: "00000000-0000-4000-8000-000000000001",
  full_name: "School Administrator",
  email: "admin@example.com",
  username: "school-admin",
  school_id: null,
  school_name: null,
  roles: ["ADMIN"],
};

const tokenResponse: TokenResponse = {
  access_token: "test-access-token",
  token_type: "bearer",
  expires_in: 600,
  user: authenticatedUser,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("authentication flow", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) {
        return jsonResponse({ detail: "Invalid identifier or password." }, 401);
      }
      if (url.endsWith("/auth/login")) return jsonResponse(tokenResponse);
      if (url.endsWith("/auth/logout"))
        return jsonResponse({ message: "Logged out." });
      if (url.endsWith("/admin/dashboard/stats")) {
        return jsonResponse({
          active_students: 0,
          active_teachers: 0,
          classes: 0,
          subjects: 0,
          chapters: 0,
          active_enrollments: 0,
          unenrolled_active_students: 0,
          recent_students: [],
          recent_teachers: [],
        });
      }
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("validates credentials and reports rejected logins", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/refresh")) {
        return jsonResponse({ detail: "Invalid identifier or password." }, 401);
      }
      return jsonResponse({ detail: "Invalid identifier or password." }, 401);
    });
    renderApp(<App />);

    await user.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(
      await screen.findByText("Enter your username or email."),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("Username or email"), "unknown");
    await user.type(screen.getByLabelText("Password"), "incorrect");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't sign you in with those details. Check them and try again.",
    );
  });

  it("signs in and signs out through the protected workspace", async () => {
    const user = userEvent.setup();
    renderApp(<App />);

    await user.type(
      await screen.findByLabelText("Username or email"),
      "school-admin",
    );
    await user.type(screen.getByLabelText("Password"), "correct password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Active students")).toBeInTheDocument();
    expect(screen.getByText("School Administrator")).toBeInTheDocument();
    const loginCall = fetchMock.mock.calls.find(([input]) =>
      String(input).endsWith("/auth/login"),
    );
    expect(loginCall).toBeDefined();
    expect(JSON.parse(String(loginCall?.[1]?.body))).toEqual({
      identifier: "school-admin",
      password: "correct password",
    });

    await user.click(
      within(screen.getByRole("banner")).getByRole("button", {
        name: "Sign out",
      }),
    );
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Welcome back" }),
      ).toBeInTheDocument();
    });
  });

  it("restores a refresh-cookie session without showing the login page", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/refresh"))
        return jsonResponse(tokenResponse);
      if (String(input).endsWith("/admin/dashboard/stats")) {
        return jsonResponse({
          active_students: 3,
          active_teachers: 1,
          classes: 2,
          subjects: 4,
          chapters: 8,
          active_enrollments: 3,
          unenrolled_active_students: 0,
          recent_students: [],
          recent_teachers: [],
        });
      }
      return jsonResponse({});
    });
    renderApp(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Dashboard",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Welcome back" })).toBeNull();
  });

  it("routes authenticated students to their enrolled-class learning portal", async () => {
    const user = userEvent.setup();
    const student: AuthenticatedUser = {
      ...authenticatedUser,
      full_name: "Maya Student",
      school_id: "00000000-0000-4000-8000-000000000002",
      school_name: "North School",
      roles: ["STUDENT"],
    };
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) {
        return jsonResponse({ detail: "No active session." }, 401);
      }
      if (url.endsWith("/auth/login")) {
        return jsonResponse({ ...tokenResponse, user: student });
      }
      if (url.endsWith("/student/dashboard")) {
        return jsonResponse({
          student_name: "Maya Student",
          school_name: "North School",
          enrollment: {
            class_name: "Class 8 - A",
            grade_number: 8,
            section: "A",
            academic_year: "2026-27",
          },
          subject_count: 1,
          chapter_count: 2,
          completed_quiz_count: 0,
          recent_activity: [],
          subjects: [
            {
              id: "subject-1",
              name: "Mathematics",
              code: "MATH",
              description: "Build confidence with numbers.",
              chapter_count: 2,
            },
          ],
        });
      }
      if (url.endsWith("/student/quiz/analytics")) {
        return jsonResponse({
          total_completed_quizzes: 0,
          total_questions: 0,
          total_correct_answers: 0,
          average_percentage: 0,
          highest_percentage: 0,
          recent_activity: [],
          subject_performance: [],
          chapter_performance: [],
          strongest_subjects: [],
          needs_improvement_subjects: [],
          strongest_chapters: [],
          needs_improvement_chapters: [],
        });
      }
      if (url.endsWith("/student/subjects")) {
        return jsonResponse([
          {
            id: "subject-1",
            name: "Mathematics",
            code: "MATH",
            description: "Build confidence with numbers.",
            chapter_count: 1,
          },
        ]);
      }
      if (url.endsWith("/student/subjects/subject-1")) {
        return jsonResponse({
          id: "subject-1",
          name: "Mathematics",
          code: "MATH",
          description: "Build confidence with numbers.",
          chapter_count: 1,
          chapters: [
            {
              id: "chapter-1",
              chapter_number: 1,
              title: "Rational numbers",
              description: "A foundation for working with fractions.",
              has_available_quiz: true,
            },
          ],
        });
      }
      if (url.endsWith("/student/chapters/chapter-1")) {
        return jsonResponse({
          id: "chapter-1",
          chapter_number: 1,
          title: "Rational numbers",
          description: "A foundation for working with fractions.",
          subject_id: "subject-1",
          subject_name: "Mathematics",
          class_name: "Class 8 - A",
          has_available_quiz: true,
        });
      }
      if (url.endsWith("/student/chapters/chapter-1/quiz/current")) {
        return jsonResponse({
          status: "NOT_STARTED",
          quiz_id: "quiz-1",
          quiz_title: "Rational numbers review",
          total_questions: 20,
          duration_minutes: 20,
        });
      }
      if (url.endsWith("/student/profile")) {
        return jsonResponse({
          full_name: student.full_name,
          identifier: "maya-8",
          email: student.email,
          phone: "+1 555 555 1234",
          school_name: student.school_name,
          enrollment: {
            class_name: "Class 8 - A",
            grade_number: 8,
            section: "A",
            academic_year: "2026-27",
          },
        });
      }
      return jsonResponse({});
    });

    window.history.replaceState({}, "", "/student");
    window.dispatchEvent(new PopStateEvent("popstate"));
    renderApp(<App />);
    await user.type(
      await screen.findByLabelText("Username or email"),
      "maya-8",
    );
    await user.type(screen.getByLabelText("Password"), "student password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("heading", { name: "Welcome back, Maya" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("Your performance will appear here"),
    ).toBeInTheDocument();
    expect(screen.getByText("North School")).toBeInTheDocument();
    expect(
      screen.getByText("Class 8 - A · Grade 8, Section A · 2026-27"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Mathematics/ })).toHaveAttribute(
      "href",
      "/student/subjects/subject-1",
    );
    expect(screen.getByRole("link", { name: "My subjects" })).toHaveAttribute(
      "href",
      "/student/subjects",
    );
    expect(
      screen.queryByRole("link", { name: /question bank/i }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: /Mathematics/ }));
    expect(
      await screen.findByRole("heading", { name: "Mathematics" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Course outline")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Rational numbers/ }));
    expect(
      await screen.findByRole("heading", { name: "Rational numbers" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("A foundation for working with fractions."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("A quiz is available for this chapter"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Start Quiz/ }));
    expect(
      await screen.findByRole("heading", {
        name: "Rational numbers review",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/exactly 20 questions/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Begin quiz" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "My subjects" }));
    expect(
      await screen.findByRole("heading", { name: "My subjects" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "My profile" }));
    expect(
      await screen.findByRole("heading", { name: "My profile" }),
    ).toBeInTheDocument();
    expect(screen.getByText("maya-8")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Learning hub" }));
    expect(
      await screen.findByRole("heading", { name: "More ways to learn" }),
    ).toBeInTheDocument();
  });
});
