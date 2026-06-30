import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const website = readFileSync(
  new URL("../../../backend/app/website.py", import.meta.url),
  "utf8",
);

const refreshCss = website.split("shadcn-inspired website refresh: public web only.").at(1) || "";

assert.match(refreshCss, /\.hero\s*\{[^}]*display:\s*grid;/s, "website hero should use a two-column grid on desktop");
assert.match(
  refreshCss,
  /\.hero\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*520px\)\s*minmax\(0,\s*1fr\);/s,
  "website hero should reserve a fixed text column so the product preview cannot overlap the headline",
);
assert.match(
  refreshCss,
  /\.product-visual\s*\{[^}]*position:\s*relative;[^}]*justify-self:\s*end;/s,
  "website product preview should participate in the hero grid instead of overlaying content",
);
assert.match(
  refreshCss,
  /@media\s*\(max-width:\s*1080px\)\s*\{[^}]*\.hero\s*\{[^}]*grid-template-columns:\s*1fr;/s,
  "website hero should stack at narrower desktop widths",
);
