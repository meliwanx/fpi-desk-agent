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

assert.match(
  adminApp,
  /className="model-policy-table"/,
  "admin model policy should default to a table view",
);
assert.match(
  adminApp,
  /ModelPolicyDialog/,
  "admin model policy create and edit should use a dialog component",
);
assert.match(
  adminApp,
  /\/api\/admin\/model-policy\/test/,
  "admin model policy dialog should call the backend model test endpoint",
);
assert.match(
  adminApp,
  /testState\.status !== "passed"/,
  "admin model policy dialog should block saving before a successful test",
);
assert.match(
  adminStyles,
  /\.modal-backdrop\s*{/,
  "admin model policy dialog should have modal backdrop styles",
);
assert.match(
  adminStyles,
  /\.model-policy-table\s*{/,
  "admin model policy table should have dedicated table styles",
);
