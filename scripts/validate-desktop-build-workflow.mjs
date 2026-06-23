#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import assert from "node:assert/strict";

const workflowPath = resolve(".github/workflows/desktop-build.yml");
const workflow = readFileSync(workflowPath, "utf8");
const releaseWorkflowPath = resolve(".github/workflows/release.yml");
const releaseWorkflow = readFileSync(releaseWorkflowPath, "utf8");
const signingScriptPath = resolve("scripts/sign-macos-app.sh");
const signingScript = readFileSync(signingScriptPath, "utf8");

function getJobSection(source, jobName) {
  const marker = `\n  ${jobName}:`;
  const start = source.indexOf(marker);
  assert(start >= 0, `missing job: ${jobName}`);
  const nextJob = source.slice(start + marker.length).match(/\n  [A-Za-z0-9_-]+:\n/);
  if (!nextJob) return source.slice(start);
  return source.slice(start, start + marker.length + nextJob.index);
}

const desktopWindowsJob = getJobSection(workflow, "build-windows");
const desktopMacosJob = getJobSection(workflow, "build-macos");
const releaseMacosJob = getJobSection(releaseWorkflow, "build-macos");

const requiredSnippets = [
  ["workflow name", "name: Desktop Package Build"],
  ["branch push trigger", 'branches: ["**"]'],
  ["manual trigger", "workflow_dispatch:"],
  ["Windows runner", "runs-on: windows-latest"],
  ["macOS arm runner", "runner: macos-26"],
  ["Windows installer artifact", "desktop-tauri/src-tauri/target/release/bundle/nsis/*.exe"],
  ["macOS DMG artifact", "desktop-tauri/src-tauri/target/${{ matrix.target }}/release/bundle/dmg/*.dmg"],
  ["Apple certificate secret", "APPLE_CERTIFICATE"],
  ["Apple notarization password secret", "APPLE_PASSWORD"],
  ["notarytool submission", "xcrun notarytool submit"],
  ["staple notarization ticket", "xcrun stapler staple"],
  ["Developer ID signing identity lookup", "SIGNING_IDENTITY=$(node -e"],
  ["Tauri updater artifacts enabled", "createUpdaterArtifacts"],
  ["Windows config variable", "$tauriConfig = "],
];

for (const [label, snippet] of requiredSnippets) {
  assert(
    workflow.includes(snippet),
    `desktop build workflow missing ${label}: ${snippet}`,
  );
}

for (const [label, snippet] of [
  ["desktop macOS Apple certificate secret", "APPLE_CERTIFICATE: ${{ secrets.APPLE_CERTIFICATE }}"],
  ["desktop macOS Apple ID secret", "APPLE_ID: ${{ secrets.APPLE_ID }}"],
  ["desktop macOS notarization password secret", "APPLE_PASSWORD: ${{ secrets.APPLE_PASSWORD }}"],
  ["desktop macOS certificate install", "Install Apple certificate"],
  ["desktop macOS unsigned Tauri staging build", '"macOS":{"signingIdentity":null}'],
  ["desktop macOS deterministic signing script", "scripts/sign-macos-app.sh \"$APP_PATH\" \"$SIGNING_IDENTITY\""],
  ["desktop macOS app notarization", "xcrun notarytool submit \"$ZIP_PATH\""],
  ["desktop macOS DMG notarization", "xcrun notarytool submit \"$BUNDLE_DIR/dmg/$DMG_NAME\""],
]) {
  assert(
    desktopMacosJob.includes(snippet),
    `desktop macOS job missing ${label}: ${snippet}`,
  );
}

assert(
  !desktopWindowsJob.includes("APPLE_CERTIFICATE"),
  "desktop Windows job should not include Apple signing secrets",
);

const forbiddenSnippets = [
  ["signing identity removal", "delete config.bundle.macOS.signingIdentity"],
  ["disabled updater artifacts", '"createUpdaterArtifacts":false'],
  ["disabled updater artifacts", "createUpdaterArtifacts = $false"],
  ["macOS Intel runner", "macos-26-intel"],
  ["macOS x86_64 target", "x86_64-apple-darwin"],
  ["macOS x64 artifact", "macos-x64-dmg"],
  ["macOS x64 Node runtime", "Darwin-x86_64"],
];

for (const [label, snippet] of forbiddenSnippets) {
  assert(
    !workflow.includes(snippet),
    `desktop build workflow should not include ${label}: ${snippet}`,
  );
}

for (const [label, snippet] of [
  ["release workflow stale OpenYak app path", "OpenYak.app"],
  ["release workflow stale OpenYak artifact prefix", "OpenYak_"],
]) {
  assert(
    !releaseWorkflow.includes(snippet),
    `release workflow should not include ${label}: ${snippet}`,
  );
}

for (const [label, snippet] of [
  ["release workflow dynamic product name", "APP_NAME=$(node -e"],
  ["release workflow unsigned Tauri staging build", '"macOS":{"signingIdentity":null}'],
  ["release workflow deterministic signing script", "scripts/sign-macos-app.sh \"$APP_PATH\" \"$SIGNING_IDENTITY\""],
  ["release workflow app notarization", "xcrun notarytool submit \"$ZIP_PATH\""],
  ["release workflow DMG notarization", "xcrun notarytool submit \"$BUNDLE_DIR/dmg/$DMG_NAME\""],
  ["release workflow stapler validation", "xcrun stapler validate"],
  ["release workflow signing secret preflight", "Validate Apple signing secrets"],
  ["release workflow Apple certificate secret", "APPLE_CERTIFICATE: ${{ secrets.APPLE_CERTIFICATE }}"],
]) {
  assert(
    releaseMacosJob.includes(snippet),
    `release workflow missing ${label}: ${snippet}`,
  );
}

for (const [label, snippet] of [
  ["remove stale nested signatures", "codesign --remove-signature"],
  ["remove stale bundle resource seal", "Contents/_CodeSignature"],
  ["secure timestamp verification", "Timestamp="],
  ["Developer ID authority verification", "Authority=Developer ID Application"],
  ["strict nested code verification", "verify_macho_signature"],
]) {
  assert(
    signingScript.includes(snippet),
    `macOS signing script missing ${label}: ${snippet}`,
  );
}

for (const [label, snippet] of [
  ["deep recursive app signing", "codesign --force --deep"],
  ["deep recursive app verification", "codesign -vvv --strict --deep"],
]) {
  assert(
    !workflow.includes(snippet) && !releaseWorkflow.includes(snippet),
    `workflows should not use ${label}: ${snippet}`,
  );
}
