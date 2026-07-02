import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const agentNotes = readFileSync(
  new URL("../../../AGENT.md", import.meta.url),
  "utf8",
);
const claudeNotes = readFileSync(
  new URL("../../../CLAUDE.md", import.meta.url),
  "utf8",
);
const adminStyles = readFileSync(
  new URL("../../../admin-frontend/src/styles.css", import.meta.url),
  "utf8",
);
const website = readFileSync(
  new URL("../../../backend/app/website.py", import.meta.url),
  "utf8",
);

for (const notes of [agentNotes, claudeNotes]) {
  assert.match(notes, /admin-frontend\//, "web UI notes should include the admin frontend scope");
  assert.match(notes, /backend\/app\/website\.py/, "web UI notes should include the public website scope");
  assert.match(notes, /frontend\//, "web UI notes should explicitly name the desktop client frontend");
  assert.match(notes, /desktop-tauri\//, "web UI notes should explicitly name the desktop shell");
  assert.match(notes, /Do not apply this .*desktop client|Do not apply this design system to the desktop client UI/s);
}

assert.match(adminStyles, /--primary:/, "admin web styles should use semantic design tokens");
assert.match(adminStyles, /\.nav-group-title/, "admin navigation should use grouped sections");
assert.match(website, /shadcn-inspired website refresh: public web only/, "website refresh should be scoped to public web");
assert.match(website, /class="hero-content"/, "website hero should have a stable content wrapper");
