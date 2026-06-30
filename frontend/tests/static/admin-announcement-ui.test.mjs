import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../../..");
const app = readFileSync(resolve(root, "admin-frontend/src/App.tsx"), "utf8");

assert.match(
  app,
  /\|\s*"announcements"/,
  "admin app should include an announcements tab in the Tab union",
);
assert.match(
  app,
  /key:\s*"announcements",\s*label:\s*"通知公告"/,
  "admin sidebar should expose notification announcements",
);
assert.match(
  app,
  /function AnnouncementPanel\(/,
  "admin app should render an announcement publishing panel",
);
assert.match(
  app,
  /\/api\/admin\/announcement/,
  "announcement panel should use the server-side announcement endpoint",
);
assert.match(
  app,
  /target_user_ids/,
  "announcement panel should save the selected employee target list",
);
assert.match(
  app,
  /全员/,
  "announcement panel should support all-user announcements",
);
assert.match(
  app,
  /指定员工/,
  "announcement panel should support targeted employee announcements",
);
