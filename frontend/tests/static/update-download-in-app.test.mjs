import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const updateHook = readFileSync(
  new URL("../../src/hooks/use-update-check.ts", import.meta.url),
  "utf8",
);
const updateBanner = readFileSync(
  new URL("../../src/components/desktop/update-banner.tsx", import.meta.url),
  "utf8",
);
const updateDialog = readFileSync(
  new URL("../../src/components/desktop/update-dialog.tsx", import.meta.url),
  "utf8",
);
const mainLayout = readFileSync(
  new URL("../../src/app/(main)/layout.tsx", import.meta.url),
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
const tauriConfig = readFileSync(
  new URL("../../../desktop-tauri/src-tauri/tauri.conf.json", import.meta.url),
  "utf8",
);
const desktopBuildWorkflow = readFileSync(
  new URL("../../../.github/workflows/desktop-build.yml", import.meta.url),
  "utf8",
);

// --- Hook: two-step signed updater flow with explicit install timing -------

assert.doesNotMatch(
  updateHook,
  /openExternal\(downloadUrl\)/,
  "enterprise app updates should not open the package URL in an external browser",
);

assert.match(
  updateHook,
  /@tauri-apps\/plugin-updater/,
  "enterprise app updates should use Tauri's native updater for in-app installation",
);

assert.match(
  updateHook,
  /\.download\(/,
  "enterprise app updates should download the signed updater package before asking the user to install",
);

assert.match(
  updateHook,
  /\.install\(/,
  "enterprise app updates should install the already-downloaded signed updater package inside the app",
);

assert.doesNotMatch(
  updateHook,
  /\.downloadAndInstall\(/,
  "enterprise app updates should not install automatically before the user chooses the restart/install timing",
);

assert.match(
  updateHook,
  /@tauri-apps\/plugin-process/,
  "enterprise app updates should relaunch after the updater installs the new version",
);

assert.match(
  updateHook,
  /relaunch\(/,
  "enterprise app updates should restart the app after successful in-app installation",
);

assert.match(
  updateHook,
  /event\.event === "Started"[\s\S]+event\.event === "Progress"[\s\S]+event\.event === "Finished"/,
  "enterprise app updates should translate Tauri updater download events into progress UI",
);

assert.match(
  updateHook,
  /"downloaded"/,
  "enterprise app updates should enter a downloaded confirmation state before installing",
);

assert.match(
  updateHook,
  /installOnRestart/,
  "enterprise app updates should support deferring the install to the next restart",
);

assert.match(
  updateHook,
  /PENDING_INSTALL_KEY/,
  "deferred Windows installs should persist a pending marker for the next startup",
);

assert.match(
  updateHook,
  /resumePendingInstall/,
  "deferred installs should resume automatically on the next startup",
);

assert.match(
  updateHook,
  /platform === "windows"[\s\S]+savePendingInstall/,
  "Windows should defer the NSIS install to the next startup instead of quitting immediately",
);

assert.match(
  updateHook,
  /state\.phase !== "idle"\)\s*\{\s*return update;/,
  "scheduled update re-checks must not clobber an in-flight download or ready-to-install state",
);

assert.doesNotMatch(
  updateHook,
  /downloadManualUpdatePackage|PENDING_MANUAL_UPDATE_PATH_KEY|downloadUpdatePackage|applyDownloadedUpdate|downloadUpdateAndOpen/,
  "enterprise app updates should not keep a manual DMG/EXE fallback path",
);

assert.match(
  updateHook,
  /download_sha256/,
  "enterprise app updates may keep backend package hashes for display and audit metadata",
);

assert.doesNotMatch(
  updateHook,
  /CURRENT_PACKAGE_SHA_KEY|current_package_sha256/,
  "enterprise app update checks should not use package hash identity to decide whether a version update is needed",
);

// --- Dialog: in-app popup with progress and install-timing choice ----------

assert.match(
  updateDialog,
  /phase === "downloading"[\s\S]+progress/,
  "the update dialog should show in-app download progress",
);

assert.match(
  updateDialog,
  /installNow[\s\S]+installOnRestart/,
  "after downloading, the dialog should offer install-now and install-on-next-restart choices",
);

assert.match(
  updateDialog,
  /forceUpdate[\s\S]+updateInstallLater/,
  "forced updates should hide the install-later choice",
);

assert.match(
  mainLayout,
  /<UpdateDialog \/>/,
  "the update dialog should be mounted in the main layout",
);

// --- Banner: floating reminder that routes into the dialog -----------------

assert.match(
  updateBanner,
  /fixed[\s\S]+bottom-4[\s\S]+left-4/,
  "non-forced enterprise updates should appear as a bottom-left floating reminder",
);

assert.match(
  updateBanner,
  /beginUpdate/,
  "the update reminder should open the in-app update dialog",
);

assert.doesNotMatch(
  updateBanner,
  /initial=\{\{\s*height:\s*0/,
  "non-forced enterprise updates should not reserve inline layout height in the main app",
);

// --- No manual DMG/EXE fallback in the desktop shell ------------------------

assert.doesNotMatch(
  tauriApi,
  /downloadUpdatePackage|applyDownloadedUpdate|downloadUpdateAndOpen/,
  "Tauri API should not expose manual update package commands for DMG/EXE fallback installs",
);

assert.doesNotMatch(
  tauriCommands,
  /pub async fn download_update_package|pub async fn download_update_and_open/,
  "Rust side should not implement a manual update package download command",
);

assert.doesNotMatch(
  tauriLib,
  /commands::download_update_package|commands::apply_downloaded_update|commands::download_update_and_open/,
  "Rust manual update package commands should not be registered with Tauri",
);

// --- Updater endpoint and signed CI artifacts -------------------------------

assert.match(
  tauriConfig,
  /\/api\/app\/update-manifest\/\{\{target\}\}\/\{\{arch\}\}\/\{\{current_version\}\}/,
  "Tauri updater should check the enterprise server manifest endpoint",
);

assert.match(
  desktopBuildWorkflow,
  /TAURI_SIGNING_PRIVATE_KEY/,
  "desktop build workflow should receive the Tauri updater signing key from secrets",
);

assert.doesNotMatch(
  desktopBuildWorkflow,
  /createUpdaterArtifacts\s*=\s*\$false|createUpdaterArtifacts":false/,
  "desktop build workflow should not disable updater artifacts",
);

assert.match(
  desktopBuildWorkflow,
  /createUpdaterArtifacts\s*=\s*\$true|createUpdaterArtifacts":true/,
  "desktop build workflow should generate signed updater artifacts",
);

assert.match(
  desktopBuildWorkflow,
  /\.exe\.sig/,
  "Windows artifacts should include the updater signature file",
);

assert.match(
  desktopBuildWorkflow,
  /\.app\.tar\.gz[\s\S]+\.app\.tar\.gz\.sig/,
  "macOS artifacts should include the updater archive and signature file",
);
