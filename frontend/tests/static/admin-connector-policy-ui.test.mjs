import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../../..");
const app = readFileSync(resolve(root, "admin-frontend/src/App.tsx"), "utf8");

assert.match(
  app,
  /\|\s*"connectors"/,
  "admin app should include a connectors tab in the Tab union",
);
assert.match(
  app,
  /"connectors",\s*"连接器管控"/,
  "admin sidebar should expose connector access control",
);
assert.match(
  app,
  /function ConnectorPolicyPanel\(/,
  "admin app should render a connector policy panel",
);
assert.match(
  app,
  /\/api\/admin\/connector-policy/,
  "connector policy panel should use the server-side policy endpoint",
);
assert.match(
  app,
  /allowed_user_ids/,
  "connector policy panel should save the per-user allow list",
);
