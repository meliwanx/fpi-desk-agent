import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const adminApp = readFileSync(
  new URL("../../../admin-frontend/src/App.tsx", import.meta.url),
  "utf8",
);
const adminStyles = readFileSync(
  new URL("../../../admin-frontend/src/styles.css", import.meta.url),
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
assert.match(adminApp, /\["analytics", "数据分析"\]/, "admin console should expose the analytics tab in navigation");
assert.match(adminApp, /\/api\/admin\/audit\/analytics\/users/, "admin analytics tab should load user analytics data");
assert.match(adminApp, /\["allInfo", "全部信息"\]/, "admin console should expose an all audit information page");
assert.match(adminApp, /\/api\/admin\/audit\/entries/, "admin all information page should load flattened audit entries");
assert.match(adminApp, /className="session-table/, "admin session audit should render sessions as a table");
assert.match(adminApp, /\/api\/admin\/feedback\/\$\{encodeURIComponent\(feedbackId\)\}/, "admin feedback page should delete feedback items");
assert.match(adminApp, /model\.enabled/, "admin model policy should expose model enable/disable state");
assert.match(adminApp, /禁用/, "admin model policy should expose a disable action instead of only deleting models");
assert.match(adminStyles, /\.app-shell\s*{[^}]*height:\s*100vh/s, "admin shell should fit the viewport height");
assert.match(adminStyles, /\.app-shell\s*{[^}]*overflow:\s*hidden/s, "admin shell should prevent document-level scrolling");
assert.match(adminStyles, /\.sidebar\s*{[^}]*height:\s*100vh/s, "admin sidebar should be constrained to the viewport");
assert.match(adminStyles, /\.sidebar\s*{[^}]*overflow:\s*hidden/s, "admin sidebar should keep its footer visible");
assert.match(adminStyles, /\.nav\s*{[^}]*flex:\s*1\s+1\s+auto/s, "admin navigation should take the remaining sidebar space");
assert.match(adminStyles, /\.nav\s*{[^}]*min-height:\s*0/s, "admin navigation should be allowed to shrink before scrolling");
assert.match(adminStyles, /\.nav\s*{[^}]*overflow-y:\s*auto/s, "admin navigation should scroll inside the sidebar");
assert.match(adminStyles, /\.sidebar-footer\s*{[^}]*flex-shrink:\s*0/s, "admin account controls should stay pinned in the sidebar");
assert.match(adminStyles, /\.content\s*{[^}]*height:\s*100vh/s, "admin content should be constrained to the viewport");
assert.match(adminStyles, /\.content\s*{[^}]*overflow-y:\s*auto/s, "admin content should scroll independently from the sidebar");
assert.match(adminStyles, /\.audit-workspace\s*{[^}]*overflow:\s*hidden/s, "admin audit pages should keep scrolling inside their panels");
assert.match(adminStyles, /\.table-scroll\s*{[^}]*overflow:\s*auto/s, "admin audit tables should scroll internally");
assert.match(adminStyles, /\.audit-detail\s*{[^}]*overflow:\s*auto/s, "admin audit details should scroll internally");
