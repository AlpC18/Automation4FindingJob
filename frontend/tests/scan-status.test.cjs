const test = require("node:test");
const assert = require("node:assert/strict");
const { parseTimestamp, formatTimestamp, jobFreshness, linkStatus } = require("../src/lib/scan-status.cjs");

const NOW = Date.UTC(2026, 9, 10, 12, 0, 0);

test("parses epoch seconds and naive UTC database timestamps", () => {
  assert.equal(parseTimestamp(1791100433.86).toISOString(), "2026-10-04T07:53:53.860Z");
  assert.equal(parseTimestamp("2026-10-04 07:53:53").toISOString(), "2026-10-04T07:53:53.000Z");
  assert.equal(parseTimestamp("2026-10-04T07:53:53Z").toISOString(), "2026-10-04T07:53:53.000Z");
});

test("missing or invalid timestamps never render as raw values", () => {
  for (const value of [null, undefined, "", "Henüz çalışmadı"]) assert.equal(formatTimestamp(value, "tr"), "—");
  assert.notEqual(formatTimestamp(1791100433.86, "tr"), "1791100433.86");
});

test("freshness separates stale, aging and fresh listings", () => {
  assert.deepEqual(jobFreshness({ stale_at: "2026-10-09 00:00:00", last_seen_at: "2026-10-09 00:00:00" }, NOW), { level: "stale", days: null });
  assert.deepEqual(jobFreshness({ last_seen_at: "2026-10-01 12:00:00" }, NOW), { level: "aging", days: 9 });
  assert.deepEqual(jobFreshness({ last_seen_at: "2026-10-09 12:00:00" }, NOW), { level: "fresh", days: 1 });
  assert.deepEqual(jobFreshness({}, NOW), { level: "unknown", days: null });
});

test("unknown link states fall back to unchecked instead of looking verified", () => {
  assert.equal(linkStatus({ status: "reachable" }), "reachable");
  assert.equal(linkStatus({ status: "blocked" }), "blocked");
  assert.equal(linkStatus({ status: "unknown" }), "unchecked");
  assert.equal(linkStatus(null), "unchecked");
});
