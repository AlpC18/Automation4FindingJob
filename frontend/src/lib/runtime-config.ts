export interface RuntimeConfig {
  apiBaseUrl?: string;
  apiAuthToken?: string;
  multiTenantEnabled?: boolean;
}

declare global {
  interface Window {
    __CAREER_AGENT_CONFIG__?: RuntimeConfig;
  }
}

const buildTimeConfig: RuntimeConfig = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api",
  apiAuthToken: process.env.NEXT_PUBLIC_API_AUTH_TOKEN || "",
};

export function getRuntimeConfig(): RuntimeConfig {
  if (typeof window === "undefined") return buildTimeConfig;
  return { ...buildTimeConfig, ...(window.__CAREER_AGENT_CONFIG__ || {}) };
}

export function getApiBaseUrl(): string {
  return (getRuntimeConfig().apiBaseUrl || "/api").replace(/\/$/, "");
}

export function getApiAuthToken(): string {
  if (getRuntimeConfig().multiTenantEnabled) return "";
  return getRuntimeConfig().apiAuthToken || "";
}

export function isMultiTenantEnabled(): boolean {
  return Boolean(getRuntimeConfig().multiTenantEnabled);
}

export function getWebSocketUrl(path = "/ws/events"): string {
  const apiUrl = getApiBaseUrl();
  const socketBase = apiUrl.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  return `${socketBase}${path.startsWith("/") ? path : `/${path}`}`;
}
