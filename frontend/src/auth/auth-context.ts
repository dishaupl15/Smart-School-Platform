import { createContext } from "react";
import type { LoginCredentials } from "@/services/auth-service";
import type { AuthenticatedUser } from "@/types/auth";

export type AuthStatus = "restoring" | "authenticated" | "unauthenticated";

export interface AuthContextValue {
  user: AuthenticatedUser | null;
  status: AuthStatus;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
