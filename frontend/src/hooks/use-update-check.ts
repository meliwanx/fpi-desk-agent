"use client";

import type { Update as TauriUpdate } from "@tauri-apps/plugin-updater";
import { useCallback, useEffect, useSyncExternalStore } from "react";
import { API, IS_DESKTOP } from "@/lib/constants";
import { getCompanySessionToken } from "@/lib/company-auth";
import { enterpriseApi } from "@/lib/enterprise-api";
import { desktopAPI } from "@/lib/tauri-api";

const CHECK_INTERVAL = 4 * 60 * 60 * 1000; // 4 hours
const STARTUP_DELAY = 5000; // 5 seconds
const DISMISSED_KEY = "fpi-agent-dismissed-update";

export interface EnterpriseUpdatePolicy {
  enabled: boolean;
  current_version: string;
  latest_version: string;
  min_supported_version: string;
  update_available: boolean;
  force_update: boolean;
  release_notes: string;
  latest_package_id?: string;
  latest_package_name?: string;
  latest_package_sha256?: string;
  latest_package_md5?: string;
  download_url: string;
  download_filename?: string;
  download_size_bytes?: number;
  download_sha256?: string;
  checked_at: string;
}

interface UpdateState {
  available: boolean;
  version: string | null;
  notes: string | null;
  forceUpdate: boolean;
  downloadUrl: string | null;
  downloadFilename: string | null;
  downloadSha256: string | null;
  downloading: boolean;
  readyToInstall: boolean;
  installing: boolean;
  progress: number;
  dismissed: boolean;
  error: string | null;
}

interface UpdateInfo extends Omit<UpdateState, "dismissed"> {
  downloadUpdate: () => Promise<void>;
  installNow: () => Promise<void>;
  installLater: () => Promise<void>;
  dismiss: () => void;
  checkNow: () => Promise<EnterpriseUpdatePolicy | null>;
}

let state: UpdateState = {
  available: false,
  version: null,
  notes: null,
  forceUpdate: false,
  downloadUrl: null,
  downloadFilename: null,
  downloadSha256: null,
  downloading: false,
  readyToInstall: false,
  installing: false,
  progress: 0,
  dismissed: false,
  error: null,
};

const listeners = new Set<() => void>();
let pendingUpdate: EnterpriseUpdatePolicy | null = null;
let pendingTauriUpdate: TauriUpdate | null = null;
let initialized = false;

function setState(patch: Partial<UpdateState>) {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
}

function subscribe(callback: () => void) {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
}

export async function checkForUpdates(): Promise<EnterpriseUpdatePolicy | null> {
  if (!IS_DESKTOP) return null;
  try {
    const [{ getVersion }, platform] = await Promise.all([
      import("@tauri-apps/api/app"),
      desktopAPI.getPlatform().catch(() => ""),
    ]);
    const currentVersion = await getVersion();
    const query = new URLSearchParams({
      current_version: currentVersion,
      platform,
    });
    const update = await enterpriseApi.get<EnterpriseUpdatePolicy>(
      `${API.APP.UPDATE_POLICY}?${query.toString()}`,
      { timeoutMs: 15_000 },
    );
    pendingUpdate = update;

    if (!update.enabled || !update.update_available) {
      setState({
        available: false,
        version: update.latest_version || null,
        notes: update.release_notes || null,
        forceUpdate: false,
        downloadUrl: update.download_url || null,
        downloadFilename: update.download_filename || null,
        downloadSha256: update.download_sha256 || null,
        downloading: false,
        readyToInstall: false,
        installing: false,
        progress: 0,
        dismissed: false,
        error: null,
      });
      return update;
    }

    const dismissedVersion = localStorage.getItem(DISMISSED_KEY);
    if (!update.force_update && dismissedVersion === update.latest_version) {
      setState({
        available: false,
        version: update.latest_version,
        notes: update.release_notes || null,
        forceUpdate: false,
        downloadUrl: update.download_url || null,
        downloadFilename: update.download_filename || null,
        downloadSha256: update.download_sha256 || null,
        readyToInstall: false,
        installing: false,
        dismissed: true,
        error: null,
      });
      return update;
    }

    setState({
      available: true,
      version: update.latest_version,
      notes: update.release_notes || null,
      forceUpdate: update.force_update,
      downloadUrl: update.download_url || null,
      downloadFilename: update.download_filename || null,
      downloadSha256: update.download_sha256 || null,
      readyToInstall: false,
      installing: false,
      dismissed: false,
      error: null,
    });
    return update;
  } catch (error) {
    console.warn("Update check failed:", error);
    const message = error instanceof Error ? error.message : String(error);
    setState({ error: message, downloading: false });
    return null;
  }
}

function updaterAuthHeaders(): Record<string, string> | undefined {
  const token = getCompanySessionToken();
  return token ? { "X-FPI-Session": token } : undefined;
}

function clampProgress(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function closePendingTauriUpdate() {
  void pendingTauriUpdate?.close().catch((error) => {
    console.warn("Failed to close pending updater resource:", error);
  });
  pendingTauriUpdate = null;
}

async function downloadWithTauriUpdater(): Promise<boolean> {
  const { check } = await import("@tauri-apps/plugin-updater");
  const headers = updaterAuthHeaders();
  const update = await check({ headers, timeout: 15_000 });
  if (!update) return false;

  closePendingTauriUpdate();
  pendingTauriUpdate = update;

  let downloaded = 0;
  let total = 0;
  await update.download((event) => {
    if (event.event === "Started") {
      downloaded = 0;
      total = event.data.contentLength || 0;
      setState({ progress: total > 0 ? 1 : 0 });
    } else if (event.event === "Progress") {
      downloaded += event.data.chunkLength;
      if (total > 0) {
        setState({ progress: clampProgress((downloaded / total) * 100) });
      }
    } else if (event.event === "Finished") {
      setState({ progress: 100 });
    }
  }, { headers, timeout: 30 * 60 * 1000 });

  setState({ progress: 100 });
  return true;
}

async function downloadUpdate() {
  setState({ downloading: true, readyToInstall: false, installing: false, error: null, progress: 0 });
  try {
    const downloadedInApp = await downloadWithTauriUpdater();
    if (downloadedInApp) {
      setState({
        downloading: false,
        readyToInstall: true,
        progress: 100,
      });
      return;
    }
    setState({
      error: "未找到签名的应用内更新包，请在后台上传 Tauri updater 包和 .sig 签名文件。",
      downloading: false,
      readyToInstall: false,
      progress: 0,
    });
  } catch (updaterError) {
    console.warn("In-app updater failed:", updaterError);
    closePendingTauriUpdate();
    const message = updaterError instanceof Error ? updaterError.message : String(updaterError);
    setState({ error: message, downloading: false, readyToInstall: false });
  }
}

async function installDownloadedUpdate(relaunchAfterInstall: boolean) {
  if (!state.readyToInstall) {
    await downloadUpdate();
  }
  if (!pendingTauriUpdate) {
    setState({
      error: "更新包还没有下载完成，请先下载更新包。",
      downloading: false,
      installing: false,
      readyToInstall: false,
    });
    return;
  }
  setState({ installing: true, error: null });
  try {
    const update = pendingTauriUpdate;
    await update.install();
    pendingTauriUpdate = null;
    await update.close().catch((error) => {
      console.warn("Failed to close installed updater resource:", error);
    });

    if (relaunchAfterInstall) {
      const { relaunch } = await import("@tauri-apps/plugin-process");
      await relaunch();
      return;
    }

    rememberDismissedUpdate();
    setState({
      available: false,
      readyToInstall: false,
      installing: false,
      dismissed: true,
    });
  } catch (error) {
    console.error("Update install failed:", error);
    const message = error instanceof Error ? error.message : String(error);
    setState({ error: message, installing: false });
  }
}

async function installNow() {
  await installDownloadedUpdate(true);
}

async function installLater() {
  await installDownloadedUpdate(false);
}

function rememberDismissedUpdate() {
  const version = pendingUpdate?.latest_version || state.version;
  if (version) localStorage.setItem(DISMISSED_KEY, version);
}

function dismiss() {
  if (state.forceUpdate) return;
  rememberDismissedUpdate();
  setState({ dismissed: true, available: false });
}

function initOnce() {
  if (initialized || !IS_DESKTOP) return;
  initialized = true;
  setTimeout(() => void checkForUpdates(), STARTUP_DELAY);
  setInterval(() => void checkForUpdates(), CHECK_INTERVAL);
  desktopAPI.onCheckForUpdates(() => {
    void checkForUpdates();
  });
}

const serverSnapshot: UpdateState = {
  available: false,
  version: null,
  notes: null,
  forceUpdate: false,
  downloadUrl: null,
  downloadFilename: null,
  downloadSha256: null,
  downloading: false,
  readyToInstall: false,
  installing: false,
  progress: 0,
  dismissed: false,
  error: null,
};

export function useUpdateCheck(): UpdateInfo {
  useEffect(() => {
    initOnce();
  }, []);

  const snapshot = useSyncExternalStore(
    subscribe,
    () => state,
    () => serverSnapshot,
  );
  const boundDownload = useCallback(() => downloadUpdate(), []);
  const boundInstallNow = useCallback(() => installNow(), []);
  const boundInstallLater = useCallback(() => installLater(), []);
  const boundDismiss = useCallback(() => dismiss(), []);
  const boundCheck = useCallback(() => checkForUpdates(), []);

  return {
    available: snapshot.available && !snapshot.dismissed,
    version: snapshot.version,
    notes: snapshot.notes,
    forceUpdate: snapshot.forceUpdate,
    downloadUrl: snapshot.downloadUrl,
    downloadFilename: snapshot.downloadFilename,
    downloadSha256: snapshot.downloadSha256,
    downloading: snapshot.downloading,
    readyToInstall: snapshot.readyToInstall,
    installing: snapshot.installing,
    progress: snapshot.progress,
    error: snapshot.error,
    downloadUpdate: boundDownload,
    installNow: boundInstallNow,
    installLater: boundInstallLater,
    dismiss: boundDismiss,
    checkNow: boundCheck,
  };
}
