import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const adminApp = readFileSync(
  new URL("../../../admin-frontend/src/App.tsx", import.meta.url),
  "utf8",
);

assert.match(adminApp, /daily_active_users/, "admin overview should render daily active user metrics");
assert.match(adminApp, /online_sessions/, "admin overview should render online session metrics");
assert.match(adminApp, /\/api\/admin\/sessions/, "admin users page should load company login sessions");
assert.match(adminApp, /\/api\/admin\/sessions\/revoke-bulk/, "admin users page should support bulk session revocation");
assert.match(adminApp, /\/api\/admin\/sessions\/\$\{encodeURIComponent\(sessionId\)\}\/revoke/, "admin users page should revoke one session");
assert.match(adminApp, /\/api\/admin\/audit\/admin-actions/, "admin console should expose administrator action logs");
assert.match(adminApp, /selectedSessionIds/, "admin users page should track selected sessions for batch operations");
assert.match(adminApp, /踢下线/, "admin users page should expose kick-offline actions in Chinese UI");
assert.match(adminApp, /管控日志/, "admin console should show administrator control logs in Chinese UI");
