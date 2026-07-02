import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const backendRs = readFileSync(
  new URL("../../../desktop-tauri/src-tauri/src/backend.rs", import.meta.url),
  "utf8",
);
const tauriConfig = JSON.parse(
  readFileSync(
    new URL("../../../desktop-tauri/src-tauri/tauri.conf.json", import.meta.url),
    "utf8",
  ),
);

// The chat database lives under <app-data>/<bundle identifier>/data, so a
// rebrand that changes the identifier silently orphans every user's chats.
// v1.4.0 shipped as com.openyak.desktop; the desktop shell must migrate that
// data forward on startup.

assert.match(
  backendRs,
  /LEGACY_BUNDLE_IDENTIFIERS[\s\S]*com\.openyak\.desktop/,
  "the desktop shell must remember previous bundle identifiers for data migration",
);

assert.match(
  backendRs,
  /fn migrate_legacy_app_data/,
  "the desktop shell must migrate chat data from previous bundle identifiers",
);

assert.match(
  backendRs,
  /migrate_legacy_app_data\(&app_data_dir, &desktop_log_path\)/,
  "legacy data migration must run during backend startup before the data dir is used",
);

assert.match(
  backendRs,
  /openyak\.db/,
  "migration must key off the chat SQLite database location",
);

assert.notEqual(
  tauriConfig.identifier,
  "com.openyak.desktop",
  "current identifier should differ from the legacy one this test guards",
);

assert.ok(
  !backendRs.includes(`"${tauriConfig.identifier}"`) ||
    !backendRs.match(/LEGACY_BUNDLE_IDENTIFIERS[^;]*"com\.fpiagent\.desktop"/),
  "the current bundle identifier must not be listed as a legacy identifier",
);
