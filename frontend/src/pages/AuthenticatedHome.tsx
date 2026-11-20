import { LogOut } from "lucide-react";
import { useAuth } from "@/auth/useAuth";
import { useState } from "react";
import { Navigate } from "react-router-dom";

export function AuthenticatedHome() {
  const { user, logout } = useAuth();
  const [logoutError, setLogoutError] = useState("");

  if (user?.roles.includes("ADMIN")) return <Navigate to="/admin" replace />;
  if (user?.roles.includes("STUDENT")) return <Navigate to="/student" replace />;
  if (user?.roles.includes("TEACHER")) return <Navigate to="/teacher" replace />;

  const handleLogout = async () => {
    setLogoutError("");
    try {
      await logout();
    } catch {
      setLogoutError(
        "Your session was cleared from this browser, but the server could not confirm logout.",
      );
    }
  };

  return (
    <section className="workspace-card">
      <div className="eyebrow">Authenticated workspace</div>
      <h1>Welcome, {user?.full_name}</h1>
      <p>
        Your sign-in is active. Learning and assessment features will appear
        here.
      </p>
      <div className="role-list" aria-label="Assigned roles">
        {user?.roles.map((role) => (
          <span className="role-badge" key={role}>
            {role}
          </span>
        ))}
      </div>
      {user?.school_name && (
        <p className="school-context">{user.school_name}</p>
      )}
      {logoutError && (
        <p role="alert" className="auth-error">
          {logoutError}
        </p>
      )}
      <button className="secondary-action" onClick={() => void handleLogout()}>
        <LogOut aria-hidden="true" size={16} />
        Sign out
      </button>
    </section>
  );
}
