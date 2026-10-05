import { getApiAuthToken, getApiBaseUrl, isMultiTenantEnabled } from "./runtime-config";

// Kept for backwards-compatible imports; request functions resolve runtime
// configuration on every call so a single image can move between environments.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
export const API_AUTH_TOKEN = process.env.NEXT_PUBLIC_API_AUTH_TOKEN || "";
let sessionCsrfToken: string | null = null;

export function setApiCsrfToken(token: string | null) {
  sessionCsrfToken = token;
}

export function getApiCsrfToken() {
  return sessionCsrfToken;
}

export function buildApiUrl(endpoint: string): string {
  const url = `${getApiBaseUrl()}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  const token = getApiAuthToken();
  if (!token) return url;
  return `${url}${url.includes('?') ? '&' : '?'}api_key=${encodeURIComponent(token)}`;
}

export async function requestFromApi(endpoint: string, options?: RequestInit): Promise<Response> {
  const url = `${getApiBaseUrl()}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  const token = getApiAuthToken();
  const isFormData = typeof FormData !== "undefined" && options?.body instanceof FormData;
  const res = await fetch(url, {
      ...options,
      credentials: "include",
      headers: {
        ...(!isFormData ? { "Content-Type": "application/json" } : {}),
        ...(token ? { "X-API-Key": token } : {}),
        ...(isMultiTenantEnabled() && ["POST", "PUT", "PATCH", "DELETE"].includes((options?.method || "GET").toUpperCase()) && sessionCsrfToken
          ? { "X-CSRF-Token": sessionCsrfToken }
          : {}),
        ...options?.headers,
      },
  });
  if (!res.ok) {
    if (res.status === 401 && isMultiTenantEnabled() && typeof window !== "undefined") {
      setApiCsrfToken(null);
      window.dispatchEvent(new Event("career-agent:session-expired"));
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    // FastAPI validation errors arrive as a list of {msg}; show their text instead of "[object Object]".
    const detail = Array.isArray(err.detail) ? err.detail.map((item: any) => item?.msg || String(item)).join("; ") : err.detail;
    throw new Error((typeof detail === "string" && detail) || `Request failed with status ${res.status}`);
  }
  return res;
}

export async function fetchFromApi<T = any>(endpoint: string, options?: RequestInit): Promise<T> {
  try {
    const res = await requestFromApi(endpoint, options);
    return res.json();
  } catch (error: any) {
    console.error(`API Error on ${endpoint}:`, error);
    throw error;
  }
}

export async function waitForBackgroundJob(
  jobId: string,
  { timeoutMs = 180_000, intervalMs = 1_500 }: { timeoutMs?: number; intervalMs?: number } = {},
): Promise<any | null> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const response = await fetchFromApi<{ job?: any }>(`/tasks/jobs/${encodeURIComponent(jobId)}`);
    const job = response.job;
    if (!job) throw new Error("Background job was not found.");
    if (job.status === "succeeded") return job.result || {};
    if (job.status === "failed") throw new Error(job.error_text || "Background job failed.");
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }
  return null;
}
