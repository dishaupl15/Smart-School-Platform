import { Navigate, Outlet, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "@/auth/useAuth";
import { LoadingState } from "@/components/LoadingState";
import type { RoleName } from "@/types/auth";

interface ProtectedRouteProps {
  roles?: RoleName[];
  children?: ReactNode;
}

export function ProtectedRoute({ roles, children }: ProtectedRouteProps) {
  const { user, status } = useAuth();
  const location = useLocation();
  if (status === "restoring") {
    return <LoadingState label="Restoring your secure session…" />;
  }
  if (!user || status !== "authenticated") {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: { pathname: location.pathname } }}
      />
    );
  }
  if (roles?.length && !roles.some((role) => user.roles.includes(role))) {
    return <Navigate to="/forbidden" replace />;
  }
  return children ? <>{children}</> : <Outlet />;
}
