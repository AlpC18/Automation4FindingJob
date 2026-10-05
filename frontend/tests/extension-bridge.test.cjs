const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const extensionDir = path.join(__dirname, "../../extension");

function createBridge({ cookie = "test-session-token", senderUrl = "https://www.linkedin.com/jobs/view/123", fetchImpl } = {}) {
  let onMessage;
  let fetchCalls = 0;
  const context = {
    URL,
    Promise,
    Set,
    String,
    JSON,
    console,
    Response,
    fetch: fetchImpl || (async () => {
      fetchCalls += 1;
      return new Response(JSON.stringify({ profile: { full_name: "Test Candidate" } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
    chrome: {
      runtime: {
        getURL: () => "chrome-extension://test-extension/",
        onMessage: { addListener: (listener) => { onMessage = listener; } },
      },
      storage: {
        local: {
          get: (defaults, callback) => callback(defaults),
          set: async () => undefined,
        },
      },
      cookies: {
        get: (_options, callback) => callback(cookie ? { value: cookie } : null),
      },
    },
  };
  context.importScripts = (...files) => {
    for (const file of files) {
      vm.runInNewContext(fs.readFileSync(path.join(extensionDir, file), "utf8"), context, { filename: file });
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(extensionDir, "background.js"), "utf8"), context, { filename: "background.js" });

  return {
    context,
    get fetchCalls() { return fetchCalls; },
    request(message, url = senderUrl) {
      return new Promise((resolve) => {
        const keepChannelOpen = onMessage(message, { url, tab: url.startsWith("chrome-extension://") ? undefined : { url } }, resolve);
        if (!keepChannelOpen) resolve(undefined);
      });
    },
  };
}

test("extension API bridge uses the app session privately and returns only API data", async () => {
  let requestOptions;
  const bridge = createBridge({ fetchImpl: async (_url, options) => {
    requestOptions = options;
    return new Response(JSON.stringify({ profile: { full_name: "Test Candidate" } }), { status: 200 });
  } });

  const result = await bridge.request({ type: "career-agent-api-request", method: "GET", endpoint: "/setup/profile" });

  assert.equal(result.ok, true);
  assert.equal(result.data.profile.full_name, "Test Candidate");
  assert.equal(requestOptions.headers.Authorization, "Bearer test-session-token");
  assert.equal(JSON.stringify(result).includes("test-session-token"), false);
});

test("extension API bridge rejects unapproved sites and API paths", async () => {
  const bridge = createBridge();
  const unapprovedSite = await bridge.request(
    { type: "career-agent-api-request", method: "GET", endpoint: "/setup/profile" },
    "https://example.com/",
  );
  const unapprovedPath = await bridge.request({
    type: "career-agent-api-request", method: "POST", endpoint: "/auth/login", body: { password: "nope" },
  });

  assert.equal(unapprovedSite.status, 403);
  assert.equal(unapprovedPath.status, 403);
  assert.equal(bridge.fetchCalls, 0);
});

test("extension API bridge requires an active career-panel session", async () => {
  const bridge = createBridge({ cookie: "" });
  const result = await bridge.request({
    type: "career-agent-api-request", method: "GET", endpoint: "/setup/profile",
  });

  assert.equal(result.status, 401);
  assert.equal(bridge.fetchCalls, 0);
});

test("extension addresses stay on local HTTP and reject credential-bearing URLs", async () => {
  const bridge = createBridge();
  const config = bridge.context.CareerAgentExtensionConfig;
  const saved = await config.save("http://127.0.0.1:18000/api", "http://localhost:13000");
  assert.equal(saved.apiBaseUrl, "http://127.0.0.1:18000/api");
  await assert.rejects(config.save("https://example.com/api", "http://localhost:13000"));
  await assert.rejects(config.save("http://user:secret@localhost:18000/api", "http://localhost:13000"));
});
