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
assert.doesNotMatch(
  chatForm,
  /if \(!isLoading && connectors\.length === 0\) return null/,
  "connector selector should remain visible so users can actively refresh after admin grants access",
);
assert.doesNotMatch(
  chatForm,
  /if \(isLoading && !data\) return null/,
  "connector selector should expose loading and refresh UI instead of disappearing",
);
assert.match(
  chatForm,
  /refetch[^=]/,
  "connector selector should expose the query refetch function",
);
assert.match(
  chatForm,
  /connectorRefresh/,
  "connector selector should render a manual refresh action",
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
assert.match(zhChat, /"connectorRefresh": "刷新连接器"/, "Chinese chat copy should include connector refresh label");
assert.match(enChat, /"connectors": "Connectors"/, "English chat copy should include connector label");
assert.match(enChat, /"connectorRefresh": "Refresh connectors"/, "English chat copy should include connector refresh label");
