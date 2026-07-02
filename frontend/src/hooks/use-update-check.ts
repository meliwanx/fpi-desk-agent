"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import type { Update } from "@tauri-apps/plugin-updater";
import { API, IS_DESKTOP } from "@/lib/constants";
import { getCompanySessionToken } from "@/lib/company-auth";
import { enterpriseApi } from "@/lib/enterprise-api";
import { desktopAPI } from "@/lib/tauri-api";

const CHECK_INTERVAL = 4 * 60 * 60 * 1000; // 4 hours
const STARTUP_DELAY = 5000; // 5 seconds
const DISMISSED_KEY = "fpi-agent-dismissed-update";
const PENDING_INSTALL_KEY = "fpi-agent-pending-install";

export type UpdatePhase =
  | "idle"
  | "downloading"
  | "downloaded"
  | "installing"
  | "restart-pending";

export interface EnterpriseUpdatePolicy {
  enabled: boolean;
  current_version: string;
  latest_version: string;
  min_supported_version: string;
  update_available: boolean;
  force_update: boolean;
  release_notes: string;
  download_url: string;
  download_filename?: string;
  download_size_bytes?: number;
  download_sha256?: string;
  checked_at: string;
}

interface PendingInstallEntry {
  version: string;
  /** Set for the legacy installer fallback; Tauri updater re-downloads instead. */
  path?: string;
}

interface UpdateState {
  available: boolean;
  version: string | null;
  notes: string | null;
  forceUpdate: boolean;
  downloadUrl: string | null;
  downloadFilename: string | null;
  downloadSha256: string | null;
  phase: UpdatePhase;
  dialogOpen: boolean;
  progress: number;
  dismissed: boolean;
  error: string | null;
}

interface UpdateInfo extends Omit<UpdateState, "dismissed"> {
  /** True while a download or install is in flight (legacy convenience flag). */
  downloading: boolean;
  /** Open the in-app update dialog and start (or resume) the download. */
  beginUpdate: () => Promise<void>;
  /** Install the downloaded update and restart right away. */
  installNow: () => Promise<void>;
  /** Defer the installation until the next app restart. */
  installOnRestart: () => Promise<void>;
  /** Relaunch the app (used from the "ready, restart pending" state). */
  relaunchNow: () => Promise<void>;
  closeDialog: () => void;
  dismiss: () => void;
  checkNow: () => Promise<EnterpriseUpdatePolicy | null>;
}

const initialState: UpdateState = {
  available: false,
  version: null,
  notes: null,
  forceUpdate: false,
  downloadUrl: null,
  downloadFilename: null,
  downloadSha256: null,
  phase: "idle",
  dialogOpen: false,
  progress: 0,
  dismissed: false,
  error: null,
};

let state: UpdateState = { ...initialState };

const listeners = new Set<() => void>();
let pendingUpdate: EnterpriseUpdatePolicy | null = null;
let tauriUpdate: Update | null = null;
let downloadedPackagePath: string | null = null;
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

function versionTuple(value: string): number[] {
  const parts = (value || "").replace(/^[vV]/, "").match(/\d+/g) || [];
  return parts.slice(0, 4).map((part) => Number.parseInt(part, 10));
}

function compareVersions(left: string, right: string): number {
  const lhs = versionTuple(left);
  const rhs = versionTuple(right);
  const length = Math.max(lhs.length, rhs.length, 1);
  for (let i = 0; i < length; i += 1) {
    const a = lhs[i] ?? 0;
    const b = rhs[i] ?? 0;
    if (a !== b) return a < b ? -1 : 1;
  }
  return 0;
}

function readPendingInstall(): PendingInstallEntry | null {
  try {
    const raw = localStorage.getItem(PENDING_INSTALL_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PendingInstallEntry;
    return parsed && typeof parsed.version === "string" && parsed.version ? parsed : null;
  } catch {
    return null;
  }
}

function savePendingInstall(entry: PendingInstallEntry) {
  try {
    localStorage.setItem(PENDING_INSTALL_KEY, JSON.stringify(entry));
  } catch {
    // localStorage unavailable — deferred install falls back to a manual click.
  }
}

function clearPendingInstall() {
  try {
    localStorage.removeItem(PENDING_INSTALL_KEY);
  } catch {
    // Ignore.
  }
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
      dismissed: false,
      error: null,
    });
    return update;
  } catch (error) {
    console.warn("Update check failed:", error);
    const message = error instanceof Error ? error.message : String(error);
    setState({ error: message });
    return null;
  }
}

function fallbackUpdateFilename(downloadUrl: string, version: string | null): string {
  try {
    const segment = decodeURIComponent(new URL(downloadUrl).pathname.split("/").pop() || "");
    if (segment.includes(".")) return segment;
  } catch {
    // Fall through to version-based name.
  }
  return `fpi-agent-${version || "update"}.bin`;
}

function updaterAuthHeaders(): Record<string, string> | undefined {
  const token = getCompanySessionToken();
  return token ? { "X-FPI-Session": token } : undefined;
}

function clampProgress(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

/**
 * Download the signed update through Tauri's updater without installing it.
 * Returns false when the manifest reports no signed update for this platform.
 */
async function downloadWithTauriUpdater(): Promise<boolean> {
  const { check } = await import("@tauri-apps/plugin-updater");
  const headers = updaterAuthHeaders();
  const update = await check({ headers, timeout: 15_000 });
  if (!update) return false;

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

  tauriUpdate = update;
  downloadedPackagePath = null;
  return true;
}

/** Download the plain installer package (unsigned fallback) without opening it. */
async function downloadPackageFallback(): Promise<void> {
  const downloadUrl = pendingUpdate?.download_url || state.downloadUrl;
  if (!downloadUrl) {
    throw new Error("未配置可用的更新包，请在后台上传签名 updater 包或安装包");
  }
  const defaultName =
    pendingUpdate?.download_filename ||
    state.downloadFilename ||
    fallbackUpdateFilename(downloadUrl, pendingUpdate?.latest_version || state.version);
  const expectedSha256 = pendingUpdate?.download_sha256 || state.downloadSha256 || null;
  const cleanupProgress = desktopAPI.onUpdateDownloadProgress((event) => {
    setState({ progress: clampProgress(event.progress || 0) });
  });
  try {
    downloadedPackagePath = await desktopAPI.downloadUpdatePackage({
      url: downloadUrl,
      defaultName,
      expectedSha256,
    });
    tauriUpdate = null;
  } finally {
    cleanupProgress();
  }
}

async function beginUpdate(options?: { autoInstall?: boolean }): Promise<void> {
  if (!IS_DESKTOP) return;
  const autoInstall = options?.autoInstall ?? false;

  // Resume states: never restart a download that is running or already done.
  if (state.phase === "downloading" || state.phase === "installing") {
    setState({ dialogOpen: true });
    return;
  }
  if (state.phase === "restart-pending") {
    setState({ dialogOpen: true });
    return;
  }
  if (state.phase === "downloaded" && (tauriUpdate || downloadedPackagePath)) {
    setState({ dialogOpen: true, error: null });
    if (autoInstall) await installNow();
    return;
  }

  setState({ dialogOpen: true, phase: "downloading", progress: 0, error: null });
  try {
    let viaTauri = false;
    try {
      viaTauri = await downloadWithTauriUpdater();
    } catch (updaterError) {
      console.warn("In-app updater download failed, falling back to package installer:", updaterError);
    }
    if (!viaTauri) {
      await downloadPackageFallback();
    }
    setState({ phase: "downloaded", progress: 100, error: null });
    if (autoInstall) {
      await installNow();
    }
  } catch (error) {
    console.error("Update download failed:", error);
    const message = error instanceof Error ? error.message : String(error);
    setState({ phase: "idle", progress: 0, error: message });
  }
}

async function installNow(): Promise<void> {
  if (state.phase !== "downloaded" && state.phase !== "installing") return;
  setState({ phase: "installing", dialogOpen: true, error: null });
  try {
    if (tauriUpdate) {
      await tauriUpdate.install();
      clearPendingInstall();
      // Windows exits into the installer automatically; elsewhere we relaunch.
      const { relaunch } = await import("@tauri-apps/plugin-process");
      await relaunch();
      return;
    }
    if (downloadedPackagePath) {
      await desktopAPI.installDownloadedUpdate(downloadedPackagePath);
      clearPendingInstall();
      setState({ phase: "restart-pending" });
      return;
    }
    throw new Error("没有可安装的更新包，请重新下载");
  } catch (error) {
    console.error("Update install failed:", error);
    const message = error instanceof Error ? error.message : String(error);
    setState({ phase: "downloaded", error: message });
  }
}

async function installOnRestart(): Promise<void> {
  if (state.phase !== "downloaded") return;
  const targetVersion = pendingUpdate?.latest_version || state.version || "";
  try {
    if (tauriUpdate) {
      const platform = await desktopAPI.getPlatform().catch(() => "");
      if (platform !== "windows") {
        // macOS/Linux: installing now is safe — the running app keeps working
        // and the new version simply takes effect on the next launch.
        setState({ phase: "installing", error: null });
        await tauriUpdate.install();
        tauriUpdate = null;
        clearPendingInstall();
        setState({ phase: "restart-pending", dialogOpen: false });
        return;
      }
      // Windows NSIS install would close the app immediately, so defer the
      // whole install to the next startup instead.
      savePendingInstall({ version: targetVersion });
      setState({ phase: "restart-pending", dialogOpen: false });
      return;
    }
    if (downloadedPackagePath) {
      savePendingInstall({ version: targetVersion, path: downloadedPackagePath });
      setState({ phase: "restart-pending", dialogOpen: false });
      return;
    }
    throw new Error("没有可安装的更新包，请重新下载");
  } catch (error) {
    console.error("Deferred update failed:", error);
    const message = error instanceof Error ? error.message : String(error);
    setState({ phase: "downloaded", error: message });
  }
}

async function relaunchNow(): Promise<void> {
  const { relaunch } = await import("@tauri-apps/plugin-process");
  await relaunch();
}

function closeDialog() {
  if (state.phase === "installing") return;
  setState({ dialogOpen: false });
}

function dismiss() {
  if (state.forceUpdate) return;
  if (state.version) localStorage.setItem(DISMISSED_KEY, state.version);
  setState({ dismissed: true, available: false });
}

/** Complete a deferred ("install on next restart") update at startup. */
async function resumePendingInstall(): Promise<void> {
  const entry = readPendingInstall();
  if (!entry) return;
  try {
    const { getVersion } = await import("@tauri-apps/api/app");
    const currentVersion = await getVersion();
    if (compareVersions(currentVersion, entry.version) >= 0) {
      clearPendingInstall();
      return;
    }
  } catch {
    return;
  }

  if (entry.path) {
    setState({ dialogOpen: true, phase: "installing", version: state.version || entry.version, error: null });
    try {
      await desktopAPI.installDownloadedUpdate(entry.path);
      clearPendingInstall();
      setState({ phase: "restart-pending" });
      return;
    } catch (error) {
      console.warn("Stored update package unavailable, re-downloading:", error);
      clearPendingInstall();
      setState({ phase: "idle", dialogOpen: false });
    }
  }

  // No usable stored package: run the full download + install automatically,
  // but only when the server still reports the update (e.g. not offline).
  clearPendingInstall();
  if (pendingUpdate?.update_available) {
    await beginUpdate({ autoInstall: true });
  }
}

function initOnce() {
  if (initialized || !IS_DESKTOP) return;
  initialized = true;
  setTimeout(() => {
    void (async () => {
      await checkForUpdates();
      await resumePendingInstall();
    })();
  }, STARTUP_DELAY);
  setInterval(() => void checkForUpdates(), CHECK_INTERVAL);
  desktopAPI.onCheckForUpdates(() => {
    void checkForUpdates();
  });
}

const serverSnapshot: UpdateState = { ...initialState };

export function useUpdateCheck(): UpdateInfo {
  useEffect(() => {
    initOnce();
  }, []);

  const snapshot = useSyncExternalStore(
    subscribe,
    () => state,
    () => serverSnapshot,
  );
  const boundBegin = useCallback(() => beginUpdate(), []);
  const boundInstallNow = useCallback(() => installNow(), []);
  const boundInstallOnRestart = useCallback(() => installOnRestart(), []);
  const boundRelaunch = useCallback(() => relaunchNow(), []);
  const boundCloseDialog = useCallback(() => closeDialog(), []);
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
    phase: snapshot.phase,
    dialogOpen: snapshot.dialogOpen,
    downloading: snapshot.phase === "downloading" || snapshot.phase === "installing",
    progress: snapshot.progress,
    error: snapshot.error,
    beginUpdate: boundBegin,
    installNow: boundInstallNow,
    installOnRestart: boundInstallOnRestart,
    relaunchNow: boundRelaunch,
    closeDialog: boundCloseDialog,
    dismiss: boundDismiss,
    checkNow: boundCheck,
  };
}
