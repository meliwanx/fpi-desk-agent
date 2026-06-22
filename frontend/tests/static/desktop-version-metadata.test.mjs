import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const expectedVersion = "1.4.0";
const rootPackage = JSON.parse(readFileSync(new URL("../../../package.json", import.meta.url), "utf8"));
const rootPackageLock = JSON.parse(readFileSync(new URL("../../../package-lock.json", import.meta.url), "utf8"));
const frontendPackage = JSON.parse(readFileSync(new URL("../../package.json", import.meta.url), "utf8"));
const frontendPackageLock = JSON.parse(readFileSync(new URL("../../package-lock.json", import.meta.url), "utf8"));
const tauriConfig = JSON.parse(
  readFileSync(new URL("../../../desktop-tauri/src-tauri/tauri.conf.json", import.meta.url), "utf8"),
);
const cargoToml = readFileSync(
  new URL("../../../desktop-tauri/src-tauri/Cargo.toml", import.meta.url),
  "utf8",
);
const backendPyproject = readFileSync(new URL("../../../backend/pyproject.toml", import.meta.url), "utf8");

assert.equal(rootPackage.version, expectedVersion, "root package version should match the published app version");
assert.equal(rootPackageLock.version, expectedVersion, "root package-lock version should match the published app version");
assert.equal(rootPackageLock.packages[""].version, expectedVersion, "root lock package version should match");
assert.equal(frontendPackage.version, expectedVersion, "frontend package version should match the published app version");
assert.equal(frontendPackageLock.version, expectedVersion, "frontend package-lock version should match the published app version");
assert.equal(frontendPackageLock.packages[""].version, expectedVersion, "frontend lock package version should match");
assert.equal(tauriConfig.version, expectedVersion, "Tauri app version is what getVersion() reports at runtime");
assert.match(cargoToml, new RegExp(`^version = "${expectedVersion}"$`, "m"));
assert.match(backendPyproject, new RegExp(`^version = "${expectedVersion}"$`, "m"));
