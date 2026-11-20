import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "@/services/api-client";
import { getAccessToken, setAccessToken } from "@/services/auth-token";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("authenticated API requests", () => {
  afterEach(() => {
    setAccessToken(null);
    vi.unstubAllGlobals();
  });

  it("refreshes and retries protected auth endpoints with a bearer token", async () => {
    setAccessToken("expired-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Unauthorized" }, 401))
      .mockResolvedValueOnce(jsonResponse({ access_token: "refreshed-token" }))
      .mockResolvedValueOnce(jsonResponse({ id: "current-user" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ id: string }>("/auth/me")).resolves.toEqual({
      id: "current-user",
    });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(getAccessToken()).toBe("refreshed-token");
    const retryOptions = fetchMock.mock.calls[2]?.[1] as RequestInit;
    expect(new Headers(retryOptions.headers).get("Authorization")).toBe(
      "Bearer refreshed-token",
    );
  });

  it("lets the browser set the multipart content type for uploads", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ import_id: "one" }));
    vi.stubGlobal("fetch", fetchMock);
    const body = new FormData();
    body.set(
      "file",
      new File(["question"], "questions.csv", { type: "text/csv" }),
    );

    await apiRequest("/admin/questions/import/preview", {
      method: "POST",
      body,
    });

    const requestOptions = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(requestOptions.headers).has("Content-Type")).toBe(false);
  });
});
