import { config } from "@/utils/config";
import { getAccessToken, setAccessToken } from "@/services/auth-token";
import type { TokenResponse } from "@/types/auth";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let refreshRequest: Promise<string | null> | null = null;

function isPublicAuthEndpoint(path: string): boolean {
  return ["/auth/login", "/auth/refresh", "/auth/logout"].includes(path);
}

async function decodeResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = (await response.json()) as {
        detail?: string;
        error?: { message?: string };
      };
      message = body.detail ?? body.error?.message ?? message;
    } catch {
      // Keep the generic error when the response has no JSON body.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function request<T>(
  path: string,
  init: RequestInit,
  authenticated: boolean,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  if (authenticated && getAccessToken()) {
    headers.set("Authorization", `Bearer ${getAccessToken()}`);
  }

  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  return decodeResponse<T>(response);
}

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshRequest) {
    refreshRequest = request<TokenResponse>(
      "/auth/refresh",
      { method: "POST" },
      false,
    )
      .then(({ access_token }) => {
        setAccessToken(access_token);
        return access_token;
      })
      .catch(() => {
        setAccessToken(null);
        window.dispatchEvent(new Event("auth:session-expired"));
        return null;
      })
      .finally(() => {
        refreshRequest = null;
      });
  }
  return refreshRequest;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  try {
    return await request<T>(path, init, !isPublicAuthEndpoint(path));
  } catch (error) {
    if (
      !(error instanceof ApiError) ||
      error.status !== 401 ||
      isPublicAuthEndpoint(path)
    ) {
      throw error;
    }

    const refreshedToken = await refreshAccessToken();
    if (!refreshedToken) throw error;
    return request<T>(path, init, true);
  }
}

export async function apiDownload(path: string): Promise<Blob> {
  const fetchFile = () => {
    const headers = new Headers({ Accept: "*/*" });
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(`${config.apiBaseUrl}${path}`, {
      headers,
      credentials: "include",
    });
  };

  let response = await fetchFile();
  if (response.status === 401) {
    const refreshedToken = await refreshAccessToken();
    if (!refreshedToken) {
      throw new ApiError("Your session has expired.", 401);
    }
    response = await fetchFile();
  }
  if (!response.ok) {
    await decodeResponse(response);
    throw new ApiError(`Request failed (${response.status}).`, response.status);
  }
  return response.blob();
}
