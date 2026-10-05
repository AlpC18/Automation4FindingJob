#!/bin/sh
set -eu

node <<'NODE'
const fs = require("fs");

const runtimeConfig = {
  apiBaseUrl: process.env.RUNTIME_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api",
  apiAuthToken: process.env.RUNTIME_API_AUTH_TOKEN || process.env.NEXT_PUBLIC_API_AUTH_TOKEN || "",
  multiTenantEnabled: process.env.RUNTIME_MULTI_TENANT === "true",
};

const contents = `window.__CAREER_AGENT_CONFIG__ = ${JSON.stringify(runtimeConfig)};\n`;
fs.writeFileSync("/app/public/runtime-config.js", contents, "utf8");
NODE

exec "$@"
