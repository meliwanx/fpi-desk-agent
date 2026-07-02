import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const constants = readFileSync(resolve(root, "src/lib/constants.ts"), "utf8");
const hook = readFileSync(resolve(root, "src/hooks/use-announcement.ts"), "utf8");
const banner = readFileSync(resolve(root, "src/components/desktop/announcement-banner.tsx"), "utf8");
const layout = readFileSync(resolve(root, "src/app/(main)/layout.tsx"), "utf8");

assert.match(
  constants,
  /ANNOUNCEMENT:\s*"\/api\/app\/announcement"/,
  "frontend constants should expose the app announcement endpoint",
);
assert.match(
  hook,
  /enterpriseApi/,
  "announcement hook should call the enterprise control plane",
);
assert.match(
  hook,
  /refetchInterval:\s*30_000/,
  "announcement hook should poll frequently enough for timely delivery",
);
assert.match(
  hook,
  /markAnnouncementRead/,
  "announcement hook should expose a read acknowledgement mutation",
);
assert.match(
  banner,
  /我已阅读/,
  "announcement banner should require a manual read acknowledgement",
);
assert.match(
  layout,
  /<AnnouncementBanner \/>/,
  "main layout should mount the announcement banner at the top of the app",
);
