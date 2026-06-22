import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const updateHook = readFileSync(
  new URL("../../src/hooks/use-update-check.ts", import.meta.url),
  "utf8",
);

const tauriApi = readFileSync(
  new URL("../../src/lib/tauri-api.ts", import.meta.url),
  "utf8",
);
const tauriCommands = readFileSync(
  new URL("../../../desktop-tauri/src-tauri/src/commands.rs", import.meta.url),
  "utf8",
);
const tauriLib = readFileSync(
  new URL("../../../desktop-tauri/src-tauri/src/lib.rs", import.meta.url),
  "utf8",
);

assert.doesNotMatch(
  updateHook,
  /openExternal\(downloadUrl\)/,
  "enterprise app updates should not open the package URL in an external browser",
);

assert.match(
  updateHook,
  /downloadUpdateAndOpen/,
  "enterprise app updates should download and launch the installer inside the app flow",
);

assert.match(
  tauriApi,
  /downloadUpdateAndOpen: \(\{ url, defaultName \}\) =>\s*invoke/,
  "Tauri API should expose an installer download/open command",
);

assert.match(
  tauriCommands,
  /pub async fn download_update_and_open/,
  "Rust side should implement an update package download/open command",
);

assert.match(
  tauriLib,
  /commands::download_update_and_open/,
  "Rust update download/open command should be registered with Tauri",
);
