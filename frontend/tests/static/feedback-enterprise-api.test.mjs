import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const sidebarFooter = readFileSync(
  new URL("../../src/components/layout/sidebar-footer.tsx", import.meta.url),
  "utf8",
);

assert.match(
  sidebarFooter,
  /from\s+["']@\/lib\/enterprise-api["']/,
  "feedback form should use the enterprise API client so uploads go to the central server",
);

assert.doesNotMatch(
  sidebarFooter,
  /apiFetch\(["']\/api\/feedback["']/,
  "feedback form must not submit through apiFetch, which targets the local backend in desktop mode",
);
