const DAY_MS = 86_400_000;
const AGING_AFTER_DAYS = 7;

// Backend timestamps arrive as epoch seconds (source runs) or as naive UTC
// "YYYY-MM-DD HH:MM:SS" strings (SQLite CURRENT_TIMESTAMP).
function parseTimestamp(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number") return new Date(value * 1000);
  const text = String(value).trim();
  const naiveUtc = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(text);
  const date = new Date(naiveUtc ? `${text.replace(" ", "T")}Z` : text);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatTimestamp(value, locale) {
  const date = parseTimestamp(value);
  if (!date) return "—";
  return date.toLocaleString(locale === "en" ? "en-GB" : "tr-TR", { dateStyle: "medium", timeStyle: "short" });
}

// "stale": the source no longer returned the listing. "aging": nobody has
// re-confirmed it for a week. Neither proves the listing is closed.
function jobFreshness(job, now = Date.now()) {
  if (job?.stale_at) return { level: "stale", days: null };
  const lastSeen = parseTimestamp(job?.last_seen_at);
  if (!lastSeen) return { level: "unknown", days: null };
  const days = Math.max(0, Math.floor((now - lastSeen.getTime()) / DAY_MS));
  return { level: days >= AGING_AFTER_DAYS ? "aging" : "fresh", days };
}

function linkStatus(check) {
  const status = check?.status;
  return ["reachable", "broken", "unreachable", "queued", "invalid", "blocked"].includes(status) ? status : "unchecked";
}

module.exports = { parseTimestamp, formatTimestamp, jobFreshness, linkStatus };
