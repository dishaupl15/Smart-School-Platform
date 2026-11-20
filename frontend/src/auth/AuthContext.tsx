import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AuthContext, type AuthStatus } from "@/auth/auth-context";
import {
  login as loginRequest,
  logout as logoutRequest,
  restoreSession,
  type LoginCredentials,
} from "@/services/auth-service";
import { setAccessToken } from "@/services/auth-token";
import type { AuthenticatedUser } from "@/types/auth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("restoring");

  useEffect(() => {
    let mounted = true;
    const restore = async () => {
      try {
        const restoredUser = await restoreSession();
        if (mounted) {
          setUser(restoredUser);
          setStatus("authenticated");
        }
      } catch {
        setAccessToken(null);
        if (mounted) {
          setUser(null);
          setStatus("unauthenticated");
        }
      }
    };
    void restore();

    const handleExpiredSession = () => {
      setUser(null);
      setStatus("unauthenticated");
    };
    window.addEventListener("auth:session-expired", handleExpiredSession);
    return () => {
      mounted = false;
      window.removeEventListener("auth:session-expired", handleExpiredSession);
    };
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const authenticatedUser = await loginRequest(credentials);
    setUser(authenticatedUser);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  const value = useMemo(
    () => ({ user, status, login, logout }),
    [user, status, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
