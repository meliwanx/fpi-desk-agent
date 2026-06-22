import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const loginGate = readFileSync(
  new URL("../../src/components/auth/company-login-gate.tsx", import.meta.url),
  "utf8",
);

assert.doesNotMatch(
  loginGate,
  /useState\(["']admin["']\)/,
  "company login must not prefill the admin account",
);

assert.match(
  loginGate,
  /login-bg\.png/,
  "company login should use the supplied branded background image",
);

assert.match(
  loginGate,
  /function LoginWindowControls/,
  "company login should render its own window controls outside the main app layout",
);

assert.match(
  loginGate,
  /desktopAPI\.close\(\)/,
  "company login window controls should include a close action",
);

assert.match(
  loginGate,
  /X-FPI-App-Version/,
  "company login should send app version metadata for server-side session observability",
);

assert.match(
  loginGate,
  /X-FPI-Platform/,
  "company login should send platform metadata for server-side session observability",
);
