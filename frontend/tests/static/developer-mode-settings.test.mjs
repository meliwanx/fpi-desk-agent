import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const generalTab = readFileSync(resolve(root, "src/components/settings/general-tab.tsx"), "utf8");
const tauriApi = readFileSync(resolve(root, "src/lib/tauri-api.ts"), "utf8");
const rustCommands = readFileSync(resolve(root, "../desktop-tauri/src-tauri/src/commands.rs"), "utf8");
const rustLib = readFileSync(resolve(root, "../desktop-tauri/src-tauri/src/lib.rs"), "utf8");

assert.match(
  generalTab,
  /onDoubleClick=\{\(\) => setDeveloperMode\(true\)\}/,
  "version text should reveal developer mode on double-click",
);
assert.match(
  generalTab,
  /data-testid="developer-mode-panel"/,
  "developer mode should render a diagnostics panel",
);
assert.match(
  generalTab,
  /desktopAPI\.toggleDevtools\(\)/,
  "developer mode should expose a DevTools toggle",
);
assert.match(
  generalTab,
  /JSON\.stringify\(diagnostics, null, 2\)/,
  "diagnostics copy should serialize explicit diagnostic fields",
);
assert.match(
  tauriApi,
  /toggleDevtools: \(\) => Promise<void>/,
  "Tauri bridge should type the DevTools command",
);
assert.match(
  tauriApi,
  /invoke\("toggle_devtools"\)/,
  "Tauri bridge should call the Rust DevTools command",
);
assert.match(
  rustCommands,
  /pub fn toggle_devtools\(window: WebviewWindow\)/,
  "Rust command should toggle WebView DevTools",
);
assert.match(
  rustLib,
  /commands::toggle_devtools/,
  "Rust command should be registered with Tauri",
);
