import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const sidebarFooter = readFileSync(
  new URL("../../src/components/layout/sidebar-footer.tsx", import.meta.url),
  "utf8",
);

const adminApp = readFileSync(
  new URL("../../../admin-frontend/src/App.tsx", import.meta.url),
  "utf8",
);

assert.match(
  adminApp,
  /function FeedbackImagePreview[\s\S]+<img[\s\S]+className="feedback-preview-image"/,
  "admin feedback should render uploaded images inline by default",
);

assert.doesNotMatch(
  adminApp,
  /downloadFile\(item\.image_download_url/,
  "admin feedback should not require downloading images just to view them",
);

assert.match(
  adminApp,
  /headers:\s*\{\s*"X-FPI-Session": token\s*\}/,
  "admin feedback image preview should fetch images with the admin session header",
);

for (const key of [
  "feedbackSubmittedTitle",
  "feedbackSubmittedDescription",
  "feedbackClose",
  "feedbackAgain",
]) {
  assert(
    sidebarFooter.includes(key),
    `feedback success screen should reference i18n key: ${key}`,
  );
}

assert.match(
  sidebarFooter,
  /variant="outline"[\s\S]+feedbackAgain/,
  "success screen should use an outline button for submitting another feedback item",
);

assert.match(
  sidebarFooter,
  /<Button[\s\S]+feedbackClose/,
  "success screen should use a primary filled button for closing",
);
