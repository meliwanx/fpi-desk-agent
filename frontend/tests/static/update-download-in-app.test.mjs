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
  /readyToInstall/,
  "enterprise app updates should enter a ready-to-install confirmation state after the package is downloaded",
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

assert.doesNotMatch(
  updateHook,
  /localStorage\.setItem\(\s*CURRENT_PACKAGE_SHA_KEY/,
  "enterprise app updates should not mark a same-version hash as installed state",
);

assert.doesNotMatch(
  updateHook,
  /pendingUpdate\?\.latest_package_sha256|localStorage\.setItem\(\s*DISMISSED_KEY\s*,\s*[^)]*latest_package_sha256/,
  "enterprise app updates should dismiss non-forced reminders by version label, not package sha256",
);

assert.match(
  updateBanner,
  /fixed[\s\S]+bottom-4[\s\S]+left-4/,
  "non-forced enterprise updates should appear as a bottom-left floating reminder",
);

assert.match(
  updateBanner,
  /updateInstallNow[\s\S]+updateInstallLater/,
  "downloaded enterprise updates should ask whether to install immediately or on next startup",
);

assert.doesNotMatch(
  updateBanner,
  /available && readyToInstall[\s\S]+fixed inset-0/,
  "downloaded non-forced enterprise updates should not show a centered modal",
);

assert.doesNotMatch(
  updateBanner,
  /initial=\{\{\s*height:\s*0/,
  "non-forced enterprise updates should not reserve inline layout height in the main app",
);

assert.doesNotMatch(
  tauriApi,
  /downloadUpdatePackage|applyDownloadedUpdate|downloadUpdateAndOpen/,
  "Tauri API should not expose manual update package commands for DMG/EXE fallback installs",
);

assert.doesNotMatch(
  tauriApi,
  /onUpdateDownloadProgress/,
  "Tauri API should not expose manual update download progress events",
);

assert.doesNotMatch(
  tauriCommands,
  /update-download-progress/,
  "Rust should not implement a separate manual update downloader",
);

assert.doesNotMatch(
  tauriCommands,
  /actual_sha256[\s\S]+eq_ignore_ascii_case/,
  "Rust should not verify manual DMG/EXE update hashes for app updates",
);

assert.doesNotMatch(
  tauriCommands,
  /pub async fn apply_downloaded_update/,
  "Rust side should not apply downloaded DMG/EXE fallback packages",
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
