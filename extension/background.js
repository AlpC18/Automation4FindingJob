importScripts("config.js");

const ALLOWED_REQUESTS = new Set([
  "GET /scrape/health",
  "GET /scrape/linkedin_session_status",
  "GET /setup/profile",
  "POST /scrape/analyze_on_the_fly",
  "POST /scrape/seen_jobs/add",
  "POST /rank/salary/search",
  "POST /llm/generate",
  "POST /scrape/sync_linkedin_session",
]);
const ALLOWED_JOB_SITES = ["linkedin.com", "upwork.com", "kosovajob.com", "indeed.com",
  "fiverr.com", "freelancer.com", "toptal.com", "gjirafa.com", "kariyer.net", "glassdoor.com", "wellfound.com"];

function allowedSender(sender) {
  if (sender.url?.startsWith(chrome.runtime.getURL(""))) return true;
  const tabUrl = sender.tab?.url;
  if (!tabUrl) return false;
  try {
    const host = new URL(tabUrl).hostname.toLowerCase();
    return ALLOWED_JOB_SITES.some((site) => host === site || host.endsWith(`.${site}`));
  } catch {
    return false;
  }
}

function getSessionCookie(apiBaseUrl) {
  const apiOrigin = new URL(apiBaseUrl).origin;
  return new Promise((resolve) => {
    chrome.cookies.get({ url: apiOrigin, name: "career_session" }, (cookie) => {
      resolve(cookie?.value || "");
    });
  });
}

async function proxyApiRequest(message) {
  const method = String(message.method || "GET").toUpperCase();
  const endpoint = String(message.endpoint || "");
  if (!ALLOWED_REQUESTS.has(`${method} ${endpoint}`)) {
    return { ok: false, status: 403, error: "Bu eklenti isteğine izin verilmiyor." };
  }

  const { apiBaseUrl } = await CareerAgentExtensionConfig.get();
  const session = await getSessionCookie(apiBaseUrl);
  if (!session) {
    return { ok: false, status: 401, error: "Önce kariyer panelinde oturum aç." };
  }

  const response = await fetch(`${apiBaseUrl}${endpoint}`, {
    method,
    headers: {
      Authorization: `Bearer ${session}`,
      ...(message.body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(message.body === undefined ? {} : { body: JSON.stringify(message.body) }),
  });
  const data = await response.json().catch(() => ({}));
  return response.ok
    ? { ok: true, status: response.status, data }
    : { ok: false, status: response.status, error: data.detail || "İstek tamamlanamadı." };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "career-agent-api-request") return false;
  if (!allowedSender(sender)) {
    sendResponse({ ok: false, status: 403, error: "Bu site eklenti erişimi için izinli değil." });
    return false;
  }
  proxyApiRequest(message)
    .then(sendResponse)
    .catch(() => sendResponse({ ok: false, status: 503, error: "Backend bağlantısı kurulamadı." }));
  return true;
});
