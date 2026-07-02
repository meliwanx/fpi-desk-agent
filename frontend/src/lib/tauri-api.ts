/**
 * Tauri API bridge — replaces the Electron preload API.
 *
 * Uses Tauri's `invoke` and `listen` under the hood.
 */

import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export interface TrayRecent {
  id: string;
  title: string | null;
}

export interface UpdateDownloadProgress {
  downloaded: number;
  total?: number | null;
  progress: number;
}

export interface DesktopAPI {
  getBackendUrl: () => Promise<string>;
  getBackendToken: () => Promise<string>;
  getPendingNavigation: () => Promise<string | null>;
  getPlatform: () => Promise<string>;
  openExternal: (url: string) => Promise<void>;
  downloadAndSave: (opts: {
    url?: string;
    data?: number[];
    defaultName: string;
    defaultDirectory?: string | null;
  }) => Promise<boolean>;
  downloadUpdateAndOpen: (opts: {
    url: string;
    defaultName: string;
    expectedSha256?: string | null;
  }) => Promise<string>;
  downloadUpdatePackage: (opts: {
    url: string;
    defaultName: string;
    expectedSha256?: string | null;
  }) => Promise<string>;
  installDownloadedUpdate: (path: string) => Promise<void>;
  minimize: () => Promise<void>;
  maximize: () => Promise<void>;
  close: () => Promise<void>;
  isMaximized: () => Promise<boolean>;
  updateTrayRecents: (recents: TrayRecent[]) => Promise<void>;
  onMaximizeChange: (callback: (maximized: boolean) => void) => () => void;
  onBackendRestarting: (callback: () => void) => () => void;
  onBackendRestart: (callback: (newUrl: string) => void) => () => void;
  onBackendCrashLog: (callback: (log: string) => void) => () => void;
  onNavigate: (callback: (path: string) => void) => () => void;
  onToggleSidebar: (callback: () => void) => () => void;
  onCheckForUpdates: (callback: () => void) => () => void;
  onUpdateDownloadProgress: (callback: (progress: UpdateDownloadProgress) => void) => () => void;
  onOpenSearch: (callback: () => void) => () => void;
}

/** Helper to turn a Tauri `listen` promise into a sync cleanup function. */
function listenSync<T>(
  event: string,
  handler: (payload: T) => void
): () => void {
  let unlisten: UnlistenFn | null = null;
  let cancelled = false;

  listen<T>(event, (e) => handler(e.payload)).then((fn) => {
    if (cancelled) {
      fn();
    } else {
      unlisten = fn;
    }
  });

  return () => {
    cancelled = true;
    unlisten?.();
  };
}

export const desktopAPI: DesktopAPI = {
  getBackendUrl: () => invoke<string>("get_backend_url"),
  getBackendToken: () => invoke<string>("get_backend_token"),
  getPendingNavigation: () => invoke<string | null>("get_pending_navigation"),
  getPlatform: () => invoke<string>("get_platform"),
  openExternal: (url) => invoke("open_external", { url }),
  downloadAndSave: ({ url, data, defaultName, defaultDirectory }) =>
    invoke<boolean>("download_and_save", { url, data, defaultName, defaultDirectory }),
  downloadUpdateAndOpen: ({ url, defaultName, expectedSha256 }) =>
    invoke<string>("download_update_and_open", { url, defaultName, expectedSha256 }),
  downloadUpdatePackage: ({ url, defaultName, expectedSha256 }) =>
    invoke<string>("download_update_package", { url, defaultName, expectedSha256 }),
  installDownloadedUpdate: (path) => invoke("install_downloaded_update", { path }),
  minimize: () => invoke("window_minimize"),
  maximize: () => invoke("window_maximize"),
  close: () => invoke("window_close"),
  isMaximized: () => invoke<boolean>("is_maximized"),
  updateTrayRecents: (recents) => invoke("update_tray_recents", { recents }),
  onMaximizeChange: (callback) =>
    listenSync<boolean>("maximize-change", callback),
  onBackendRestarting: (callback) =>
    listenSync<void>("backend-restarting", callback),
  onBackendRestart: (callback) =>
    listenSync<string>("backend-restart", callback),
  onBackendCrashLog: (callback) =>
    listenSync<string>("backend-crash-log", callback),
  onNavigate: (callback) => listenSync<string>("navigate", callback),
  onToggleSidebar: (callback) => listenSync<void>("toggle-sidebar", callback),
  onCheckForUpdates: (callback) => listenSync<void>("check-for-updates", callback),
  onUpdateDownloadProgress: (callback) =>
    listenSync<UpdateDownloadProgress>("update-download-progress", callback),
  onOpenSearch: (callback) => listenSync<void>("open-search", callback),
};
