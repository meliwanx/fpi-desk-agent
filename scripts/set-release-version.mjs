import fs from "node:fs";
import path from "node:path";

const rootDir = process.cwd();
const version = process.argv[2]?.trim();

if (!version || !/^\d+\.\d+\.\d+$/.test(version)) {
  console.error("Usage: npm run set:release-version -- <MAJOR.MINOR.PATCH>");
  console.error("Example: npm run set:release-version -- 1.4.1");
  process.exit(1);
}

function readText(relativePath) {
  return fs.readFileSync(path.join(rootDir, relativePath), "utf8");
}

function writeText(relativePath, content) {
  fs.writeFileSync(path.join(rootDir, relativePath), content);
}

function readJson(relativePath) {
  return JSON.parse(readText(relativePath));
}

function writeJson(relativePath, value) {
  writeText(relativePath, `${JSON.stringify(value, null, 2)}\n`);
}

function updatePackageJson(relativePath) {
  const payload = readJson(relativePath);
  payload.version = version;
  writeJson(relativePath, payload);
}

function updatePackageLock(relativePath) {
  const payload = readJson(relativePath);
  payload.version = version;
  if (payload.packages?.[""]) {
    payload.packages[""].version = version;
  }
  writeJson(relativePath, payload);
}

function replaceOrFail(relativePath, pattern, replacement) {
  const current = readText(relativePath);
  if (!pattern.test(current)) {
    throw new Error(`Could not find version field in ${relativePath}`);
  }
  writeText(relativePath, current.replace(pattern, replacement));
}

function updateTauriConfig() {
  const payload = readJson("desktop-tauri/src-tauri/tauri.conf.json");
  payload.version = version;
  writeJson("desktop-tauri/src-tauri/tauri.conf.json", payload);
}

function updateCargoLock() {
  const relativePath = "desktop-tauri/src-tauri/Cargo.lock";
  const current = readText(relativePath);
  const pattern = /(\[\[package\]\]\nname = "openyak-desktop"\nversion = )"[^"]+"/;
  if (!pattern.test(current)) {
    throw new Error(`Could not find openyak-desktop package in ${relativePath}`);
  }
  const next = current.replace(pattern, `$1"${version}"`);
  writeText(relativePath, next);
}

updatePackageJson("package.json");
updatePackageLock("package-lock.json");
updatePackageJson("frontend/package.json");
updatePackageLock("frontend/package-lock.json");
updateTauriConfig();
replaceOrFail("desktop-tauri/src-tauri/Cargo.toml", /^version = ".*"$/m, `version = "${version}"`);
updateCargoLock();
replaceOrFail("backend/pyproject.toml", /^version = ".*"$/m, `version = "${version}"`);

console.log(`Release version set to ${version}`);
