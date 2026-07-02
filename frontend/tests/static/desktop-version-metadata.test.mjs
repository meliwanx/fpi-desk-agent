import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFileSync } from "node:fs";

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
const releasePolicy = readFileSync(new URL("../../../docs/release-version-policy.md", import.meta.url), "utf8");
const desktopWorkflow = readFileSync(
  new URL("../../../.github/workflows/desktop-build.yml", import.meta.url),
  "utf8",
);

const expectedVersion = rootPackage.version;
assert.match(expectedVersion, /^\d+\.\d+\.\d+$/, "published app version should use SemVer MAJOR.MINOR.PATCH");
assert.equal(rootPackage.version, expectedVersion, "root package version should match the published app version");
assert.equal(rootPackageLock.version, expectedVersion, "root package-lock version should match the published app version");
assert.equal(rootPackageLock.packages[""].version, expectedVersion, "root lock package version should match");
assert.equal(frontendPackage.version, expectedVersion, "frontend package version should match the published app version");
assert.equal(frontendPackageLock.version, expectedVersion, "frontend package-lock version should match the published app version");
assert.equal(frontendPackageLock.packages[""].version, expectedVersion, "frontend lock package version should match");
assert.equal(tauriConfig.version, expectedVersion, "Tauri app version is what getVersion() reports at runtime");
assert.match(cargoToml, new RegExp(`^version = "${expectedVersion}"$`, "m"));
assert.match(backendPyproject, new RegExp(`^version = "${expectedVersion}"$`, "m"));
assert.equal(
  rootPackage.scripts["check:release-version"],
  "node frontend/tests/static/desktop-version-metadata.test.mjs",
  "root package should expose a release version check script for local and CI use",
);
assert.equal(
  rootPackage.scripts["set:release-version"],
  "node scripts/set-release-version.mjs",
  "root package should expose a script that updates every release version file",
);
assert.equal(
  existsSync(new URL("../../../scripts/set-release-version.mjs", import.meta.url)),
  true,
  "release version setter script should exist",
);
assert.match(releasePolicy, /## Release Version Policy/, "release policy should document release version rules");
assert.match(releasePolicy, /package\.json` is the single source of truth/, "release policy should name root package.json as the version source");
assert.match(releasePolicy, /npm run set:release-version -- 1\.4\.1/, "release policy should document the version bump command");
assert.match(
  releasePolicy,
  /SHA-256[\s\S]+package identity[\s\S]+latest package/i,
  "release policy should state SHA-256 package identity controls enterprise update detection",
);
assert.match(
  desktopWorkflow,
  /name: Validate release version metadata[\s\S]+npm run check:release-version/,
  "desktop packaging workflow should validate release version metadata before building installers",
);

const validateStepIndex = desktopWorkflow.indexOf("name: Validate release version metadata");
const syncStepIndex = desktopWorkflow.indexOf("name: Sync desktop metadata");
assert.ok(validateStepIndex >= 0, "desktop packaging workflow should have a release version validation step");
assert.ok(syncStepIndex >= 0, "desktop packaging workflow should have a metadata sync step");
assert.ok(
  validateStepIndex < syncStepIndex,
  "desktop packaging workflow should validate committed release metadata before sync can rewrite local files",
);
