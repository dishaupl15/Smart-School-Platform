import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/auth/useAuth";
import type { AuthenticatedUser } from "@/types/auth";
import { renderApp } from "@/test/test-utils";

vi.mock("@/auth/useAuth", () => ({ useAuth: vi.fn() }));

const authenticatedUser: AuthenticatedUser = {
  id: "00000000-0000-4000-8000-000000000001",
  full_name: "Teacher User",
  email: null,
  username: "teacher",
  school_id: null,
  school_name: null,
  roles: ["TEACHER"],
};

function renderProtectedRoute() {
  return renderApp(
    <MemoryRouter initialEntries={["/protected"]}>
      <Routes>
        <Route
          path="/protected"
          element={
            <ProtectedRoute roles={["ADMIN"]}>
              <p>Protected content</p>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<p>Login page</p>} />
        <Route path="/forbidden" element={<p>Forbidden page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReset();
  });

  it("redirects unauthenticated users to login", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      status: "unauthenticated",
      login: vi.fn(),
      logout: vi.fn(),
    });

    renderProtectedRoute();
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("denies authenticated users without an allowed role", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: authenticatedUser,
      status: "authenticated",
      login: vi.fn(),
      logout: vi.fn(),
    });

    renderProtectedRoute();
    expect(screen.getByText("Forbidden page")).toBeInTheDocument();
  });

  it("shows a loading state while restoring the session", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      status: "restoring",
      login: vi.fn(),
      logout: vi.fn(),
    });

    renderProtectedRoute();
    expect(
      screen.getByText("Restoring your secure session…"),
    ).toBeInTheDocument();
  });
});
