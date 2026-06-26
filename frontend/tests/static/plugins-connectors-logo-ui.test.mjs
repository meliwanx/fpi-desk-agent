import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const pluginsContent = readFileSync(resolve(root, "src/app/(main)/plugins/content.tsx"), "utf8");
const connectorTypes = readFileSync(resolve(root, "src/types/connectors.ts"), "utf8");

assert.match(
  connectorTypes,
  /icon_url\?: string/,
  "connector API type should expose optional icon_url metadata",
);
assert.match(
  pluginsContent,
  /function ConnectorLogo\(\{ connector \}/,
  "settings connector page should have a connector logo renderer",
);
assert.match(
  pluginsContent,
  /connector\.icon_url[\s\S]+<img/,
  "settings connector page should render connector icon_url when present",
);
assert.match(
  pluginsContent,
  /<ConnectorLogo connector=\{connector\} \/>/,
  "settings connector rows should mount the connector logo",
);
