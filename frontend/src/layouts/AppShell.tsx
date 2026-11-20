import {
  BookOpen,
  GraduationCap,
  History,
  Languages,
  LogOut,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { useLanguage } from "@/hooks/useLanguage";

export function AppShell() {
  const { t } = useTranslation();
  const { language, languages, changeLanguage } = useLanguage();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isStudent = Boolean(
    user?.roles.includes("STUDENT") && !user.roles.includes("ADMIN"),
  );
  const isTeacher = Boolean(
    user?.roles.includes("TEACHER") &&
      !user.roles.includes("ADMIN") &&
      !user.roles.includes("STUDENT"),
  );

  const handleLogout = async () => {
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch {
      navigate("/login", {
        replace: true,
        state: {
          logoutError: "We couldn't confirm sign out. Please try again.",
        },
      });
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink className="brand" to="/" aria-label={t("app.name")}>
          <span className="brand-mark">
            <GraduationCap aria-hidden="true" size={23} />
          </span>
          <span>
            <strong>{t("app.name")}</strong>
            <small>{t("app.tagline")}</small>
          </span>
        </NavLink>

        <div className="sidebar-section-label">
          {isStudent
            ? "Student portal"
            : isTeacher
              ? "Teacher workspace"
              : t("navigation.workspace")}
        </div>
        <nav aria-label={t("navigation.main")}>
          {isStudent ? (
            <>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/student"
                end
              >
                <span className="nav-indicator" />
                Overview
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/student/subjects"
              >
                <BookOpen aria-hidden="true" size={15} />
                My subjects
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/student/learning"
              >
                <Sparkles aria-hidden="true" size={15} />
                Learning hub
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/student/quiz/history"
              >
                <History aria-hidden="true" size={15} />
                Quiz history
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/student/profile"
              >
                <UserRound aria-hidden="true" size={15} />
                My profile
              </NavLink>
            </>
          ) : isTeacher ? (
            <>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/teacher"
                end
              >
                <span className="nav-indicator" />
                Dashboard
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/teacher/classes"
              >
                <GraduationCap aria-hidden="true" size={15} />
                My classes
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/teacher/students"
              >
                <UserRound aria-hidden="true" size={15} />
                My students
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/teacher/results"
              >
                <History aria-hidden="true" size={15} />
                Quiz results
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/teacher/analytics"
              >
                <BookOpen aria-hidden="true" size={15} />
                Analytics
              </NavLink>
            </>
          ) : (
            <>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                to="/"
              >
                <span className="nav-indicator" />
                {t("navigation.overview")}
              </NavLink>
              {user?.roles.includes("ADMIN") && (
                <>
                  <div className="sidebar-section-label admin-nav-label">
                    Administration
                  </div>
                  <NavLink
                    className={({ isActive }) =>
                      `nav-link${isActive ? " active" : ""}`
                    }
                    to="/admin"
                  >
                    Dashboard
                  </NavLink>
                  <NavLink
                    className={({ isActive }) =>
                      `nav-link${isActive ? " active" : ""}`
                    }
                    to="/admin/students"
                  >
                    Students
                  </NavLink>
                  <NavLink
                    className={({ isActive }) =>
                      `nav-link${isActive ? " active" : ""}`
                    }
                    to="/admin/teachers"
                  >
                    Teachers
                  </NavLink>
                  <NavLink
                    className={({ isActive }) =>
                      `nav-link${isActive ? " active" : ""}`
                    }
                    to="/admin/classes"
                  >
                    Classes
                  </NavLink>
                  <NavLink
                    className={({ isActive }) =>
                      `nav-link${isActive ? " active" : ""}`
                    }
                    to="/admin/subjects"
                  >
                    Subjects
                  </NavLink>
                  <NavLink
                    className={({ isActive }) =>
                      `nav-link${isActive ? " active" : ""}`
                    }
                    to="/admin/chapters"
                  >
                    Chapters
                  </NavLink>
                  <NavLink
                    className={({ isActive }) =>
                      `nav-link${isActive ? " active" : ""}`
                    }
                    to="/admin/enrollments"
                  >
                    Enrollments
                  </NavLink>
                  <NavLink
                    className={({ isActive }) =>
                      `nav-link${isActive ? " active" : ""}`
                    }
                    to="/admin/assignments"
                  >
                    Teacher assignments
                  </NavLink>
                  <NavLink
                    className={({ isActive }) =>
                      `nav-link${isActive ? " active" : ""}`
                    }
                    to="/admin/question-bank"
                  >
                    Question bank
                  </NavLink>
                  <NavLink
                    className={({ isActive }) =>
                      `nav-link${isActive ? " active" : ""}`
                    }
                    to="/admin/questions"
                  >
                    Browse questions
                  </NavLink>
                </>
              )}
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          <span className="status-dot" aria-hidden="true" />
          <span>{t("app.developmentShell")}</span>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-context">
            {isStudent
              ? "Student portal"
              : isTeacher
                ? "Teacher workspace"
                : t("navigation.workspace")}
          </div>
          <label className="language-control">
            <Languages aria-hidden="true" size={17} />
            <span className="sr-only">{t("language.label")}</span>
            <select
              aria-label={t("language.label")}
              value={language}
              onChange={(event) => void changeLanguage(event.target.value)}
            >
              {languages.map((language) => (
                <option key={language.code} value={language.code}>
                  {language.label}
                </option>
              ))}
            </select>
          </label>
          <div className="topbar-user">
            <span>{user?.full_name}</span>
            <button
              className="icon-action"
              onClick={() => void handleLogout()}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut aria-hidden="true" size={17} />
            </button>
          </div>
        </header>
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
