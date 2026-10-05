const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const sourcePath = path.join(__dirname, "../src/lib/runtime-config.ts");
const source = fs.readFileSync(sourcePath, "utf8");

function loadRuntimeConfig(runtimeConfig, includeWindow = true) {
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const module = { exports: {} };
  const sandbox = { module, exports: module.exports, process, window: { __CAREER_AGENT_CONFIG__: runtimeConfig } };
  if (!includeWindow) delete sandbox.window;
  vm.runInNewContext(output, sandbox, { filename: sourcePath });
  return module.exports;
}

test("multi-tenant runtime config suppresses shared API credentials and builds secure socket URL", () => {
  const runtime = loadRuntimeConfig({
    apiBaseUrl: "https://api.example.test/v1/",
    apiAuthToken: "not-for-tenant-users",
    multiTenantEnabled: true,
  });
  assert.equal(runtime.getApiBaseUrl(), "https://api.example.test/v1");
  assert.equal(runtime.getApiAuthToken(), "");
  assert.equal(runtime.getWebSocketUrl("events"), "wss://api.example.test/v1/events");
});

test("single-user runtime retains the configured API token", () => {
  const runtime = loadRuntimeConfig({ apiAuthToken: "single-user-token", multiTenantEnabled: false });
  assert.equal(runtime.getApiAuthToken(), "single-user-token");
  assert.equal(runtime.isMultiTenantEnabled(), false);
});

test("Docker never publishes the server API token to the frontend container", () => {
  const composePath = path.join(__dirname, "../../docker-compose.yml");
  const compose = fs.readFileSync(composePath, "utf8");
  const frontendService = compose.split("\n  frontend:\n")[1]?.split("\nvolumes:\n")[0] || "";
  assert.match(frontendService, /RUNTIME_API_AUTH_TOKEN:\s*\$\{PUBLIC_API_AUTH_TOKEN:-\}/);
  assert.doesNotMatch(frontendService, /(?:RUNTIME_|NEXT_PUBLIC_)API_AUTH_TOKEN:\s*\$\{API_AUTH_TOKEN/);
});

test("server rendering does not require a browser window", () => {
  const runtime = loadRuntimeConfig({}, false);
  assert.equal(runtime.getApiBaseUrl(), process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api");
});
