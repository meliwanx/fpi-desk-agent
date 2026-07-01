import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const desktopLib = readFileSync(
  new URL("../../../desktop-tauri/src-tauri/src/lib.rs", import.meta.url),
  "utf8",
);
const desktopTray = readFileSync(
  new URL("../../../desktop-tauri/src-tauri/src/tray.rs", import.meta.url),
  "utf8",
);

assert.doesNotMatch(
  desktopLib,
  /StateFlags::VISIBLE/,
  "desktop window-state must not persist hidden/visible state; close-to-tray should not make the next Windows launch tray-only",
);

assert.match(
  desktopLib,
  /fn show_main_window\(/,
  "desktop startup should use a shared main-window restore helper",
);

assert.match(
  desktopLib,
  /set_skip_taskbar\(false\)/,
  "Windows main-window restore should explicitly keep the taskbar button visible",
);

assert.match(
  desktopLib,
  /window\.unminimize\(\)/,
  "main-window restore should undo minimized state before showing the window",
);

assert.match(
  desktopTray,
  /set_skip_taskbar\(false\)/,
  "tray restore should explicitly keep the Windows taskbar button visible",
);
