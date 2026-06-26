import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const chatForm = readFileSync(resolve(root, "src/components/chat/chat-form.tsx"), "utf8");
const zhChat = readFileSync(resolve(root, "src/i18n/locales/zh/chat.json"), "utf8");
const enChat = readFileSync(resolve(root, "src/i18n/locales/en/chat.json"), "utf8");

assert.match(
  chatForm,
  /function ConnectorToggle\(\)/,
  "chat composer should expose a connector selector",
);
assert.match(
  chatForm,
  /useConnectors\(\)/,
  "connector selector should load the connector registry state",
);
assert.match(
  chatForm,
  /useConnectorToggle\(\)/,
  "connector selector should enable and disable connectors from the composer",
);
assert.match(
  chatForm,
  /<Switch[\s\S]+checked=\{connector\.enabled\}/,
  "connector selector should use switches for per-connector on/off state",
);
assert.match(
  chatForm,
  /<ConnectorToggle \/>/,
  "connector selector should be mounted in the chat action bar",
);
assert.match(
  chatForm,
  /if \(!isLoading && connectors\.length === 0\) return null/,
  "connector selector should stay hidden when the user has no authorized connectors",
);
assert.match(
  chatForm,
  /if \(isLoading && !data\) return null/,
  "connector selector should avoid flashing before authorization data loads",
);
assert.match(
  chatForm,
  /function ConnectorMenuIcon\(\{ connector \}/,
  "connector selector should render connector-specific icons",
);
assert.match(
  chatForm,
  /connector\.icon_url[\s\S]+<img/,
  "connector selector should use connector icon_url when available",
);
assert.match(zhChat, /"connectors": "连接器"/, "Chinese chat copy should include connector label");
assert.match(enChat, /"connectors": "Connectors"/, "English chat copy should include connector label");
