import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AdminDashboardPage } from "@/pages/admin/AdminDashboardPage";
import { AdminPeoplePage } from "@/pages/admin/AdminPeoplePage";
import { renderApp } from "@/test/test-utils";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("admin management pages", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders dashboard counts from the API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          active_students: 12,
          active_teachers: 3,
          classes: 4,
          subjects: 5,
          chapters: 8,
          active_enrollments: 10,
          unenrolled_active_students: 2,
          recent_students: [],
          recent_teachers: [],
        }),
      ),
    );
    renderApp(
      <MemoryRouter>
        <AdminDashboardPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Active students")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("validates and creates a student, then shows the one-time credential", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/admin/classes?") || url.endsWith("/admin/classes")) {
          return jsonResponse({
            items: [
              {
                id: "class-1",
                name: "Grade 8 A",
                grade_number: 8,
                academic_year: "2026-27",
                section: "A",
                is_active: true,
                student_count: 0,
                subjects: [],
                created_at: "2026-01-01T00:00:00Z",
              },
            ],
            total: 1,
            page: 1,
            page_size: 100,
            pages: 1,
          });
        }
        if (url.endsWith("/admin/students") && init?.method === "POST") {
          return jsonResponse(
            {
              id: "student-1",
              full_name: "New Student",
              identifier: "STU-1",
              email: null,
              phone: null,
              is_active: true,
              created_at: "2026-01-01T00:00:00Z",
              temporary_password: "one-time-secret",
            },
            201,
          );
        }
        return jsonResponse({
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
          pages: 0,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderApp(
      <MemoryRouter>
        <AdminPeoplePage kind="students" />
      </MemoryRouter>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Add student" }),
    );
    await user.click(screen.getByRole("button", { name: "Create student" }));
    expect(await screen.findByText("Enter a full name.")).toBeInTheDocument();

    await user.type(screen.getByLabelText(/Full name/), "New Student");
    await user.type(screen.getByLabelText(/Student identifier/), "STU-1");
    await user.selectOptions(
      await screen.findByRole("combobox", { name: /Initial class/ }),
      "class-1",
    );
    await user.click(screen.getByRole("button", { name: "Create student" }));

    expect(await screen.findByText("one-time-secret")).toBeInTheDocument();
    expect(screen.getByText(/shown only once/i)).toBeInTheDocument();
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([input, init]) =>
          String(input).endsWith("/admin/students") && init?.method === "POST",
      );
      expect(call).toBeDefined();
    });
  });

  it("searches the student list using the server-side filter", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/admin/students?") && url.includes("search=sara")) {
        return jsonResponse({
          items: [
            {
              id: "student-1",
              full_name: "Sara Student",
              identifier: "STU-1",
              email: null,
              phone: null,
              is_active: true,
              created_at: "2026-01-01T00:00:00Z",
              enrollment: null,
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
          pages: 1,
        });
      }
      return jsonResponse({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        pages: 0,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp(
      <MemoryRouter>
        <AdminPeoplePage kind="students" />
      </MemoryRouter>,
    );

    await user.type(
      await screen.findByPlaceholderText("Name or identifier"),
      "sara",
    );

    expect(await screen.findByText("Sara Student")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("search=sara"),
      ),
    ).toBe(true);
  });

  it("displays API errors instead of fabricated dashboard data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: "School context required." }, 403),
      ),
    );
    renderApp(
      <MemoryRouter>
        <AdminDashboardPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "School context required.",
    );
    expect(screen.queryByText("Active students")).toBeNull();
  });
});
