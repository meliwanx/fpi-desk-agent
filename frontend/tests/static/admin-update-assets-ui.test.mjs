import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const adminApp = readFileSync(
  new URL("../../../admin-frontend/src/App.tsx", import.meta.url),
  "utf8",
);

assert.match(
  adminApp,
  /\/api\/admin\/update-assets/,
  "admin update page should load the full update package history",
);

assert.match(
  adminApp,
  /packageName/,
  "admin update uploads should let admins manually name each package",
);

assert.match(
  adminApp,
  /setLatestAsset/,
  "admin update package history should let admins manually choose the latest package",
);

assert.match(
  adminApp,
  /MD5|md5/,
  "admin update package history should display MD5 alongside SHA-256",
);
