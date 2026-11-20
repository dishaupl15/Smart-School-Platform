import { apiRequest } from "@/services/api-client";
import { setAccessToken } from "@/services/auth-token";
import type { TokenResponse } from "@/types/auth";

export interface LoginCredentials {
  identifier: string;
  password: string;
  school_code?: string;
}

export async function login(credentials: LoginCredentials) {
  const response = await apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  setAccessToken(response.access_token);
  return response.user;
}

let sessionRestore: Promise<TokenResponse> | null = null;

export async function restoreSession() {
  if (!sessionRestore) {
    sessionRestore = apiRequest<TokenResponse>("/auth/refresh", {
      method: "POST",
    }).finally(() => {
      sessionRestore = null;
    });
  }
  const response = await sessionRestore;
  setAccessToken(response.access_token);
  return response.user;
}

export async function logout() {
  try {
    await apiRequest<{ message: string }>("/auth/logout", { method: "POST" });
  } finally {
    setAccessToken(null);
  }
}

export async function changePassword(
  current_password: string,
  new_password: string,
) {
  return apiRequest<{ message: string }>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password, new_password }),
  });
}
