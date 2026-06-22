#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import assert from "node:assert/strict";

const workflowPath = resolve(".github/workflows/desktop-build.yml");
const workflow = readFileSync(workflowPath, "utf8");

const requiredSnippets = [
  ["workflow name", "name: Desktop Package Build"],
  ["branch push trigger", 'branches: ["**"]'],
  ["manual trigger", "workflow_dispatch:"],
  ["Windows runner", "runs-on: windows-latest"],
  ["macOS arm runner", "runner: macos-26"],
  ["macOS Intel runner", "runner: macos-26-intel"],
  ["Windows installer artifact", "desktop-tauri/src-tauri/target/release/bundle/nsis/*.exe"],
  ["macOS DMG artifact", "desktop-tauri/src-tauri/target/${{ matrix.target }}/release/bundle/dmg/*.dmg"],
  ["Tauri updater artifacts disabled", '"createUpdaterArtifacts":false'],
];

for (const [label, snippet] of requiredSnippets) {
  assert(
    workflow.includes(snippet),
    `desktop build workflow missing ${label}: ${snippet}`,
  );
}
