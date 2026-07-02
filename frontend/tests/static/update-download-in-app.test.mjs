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
  /update\.download\(/,
  "enterprise app updates should download the signed updater package in-app with progress",
);

assert.match(
  updateHook,
  /tauriUpdate\.install\(\)/,
  "enterprise app updates should install the signed updater package instead of opening a DMG/EXE",
);

assert.match(
  updateHook,
  /installOnRestart/,
  "enterprise app updates should support deferring the install to the next restart",
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
  /downloadPackageFallback/,
  "enterprise app updates should keep the legacy package installer only as a fallback for unsigned/manual packages",
);

assert.match(
  updateHook,
  /downloadUpdatePackage/,
  "enterprise app updates should still support legacy package fallback for existing admin uploads",
);

assert.match(
  updateHook,
  /installDownloadedUpdate/,
  "enterprise app updates should install the downloaded fallback package via the Rust command",
);

assert.match(
  updateHook,
  /expectedSha256/,
  "enterprise app updates should pass the backend-provided sha256 to the native downloader",
);

assert.match(
  tauriApi,
  /downloadUpdateAndOpen: \(\{ url, defaultName, expectedSha256 \}\) =>\s*invoke/,
  "Tauri API should expose an installer download/open command for legacy fallback",
);

assert.match(
  tauriApi,
  /onUpdateDownloadProgress/,
  "Tauri API should expose update download progress events",
);

assert.match(
  tauriCommands,
  /emit\([\s\S]*"update-download-progress"/,
  "Rust update download command should emit progress events",
);

assert.match(
  tauriCommands,
  /actual_sha256[\s\S]+eq_ignore_ascii_case/,
  "Rust update download command should verify the downloaded package hash before installation",
);

assert.match(
  tauriCommands,
  /Command::new\(&file_path\)[\s\S]+\.arg\("\/S"\)/,
  "Windows legacy update installer should be launched silently instead of showing the first-install wizard",
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

assert.match(
  tauriLib,
  /commands::download_update_package[\s\S]+commands::install_downloaded_update/,
  "Rust download-only and deferred-install commands should be registered with Tauri",
);

assert.match(
  tauriCommands,
  /pub async fn download_update_package/,
  "Rust side should implement a download-only update command for the two-step install flow",
);

assert.match(
  tauriCommands,
  /pub async fn install_downloaded_update/,
  "Rust side should implement installing a previously downloaded update package",
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
