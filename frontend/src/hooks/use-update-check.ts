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

interface PendingInstallEntry {
  version: string;
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
  /** Convenience flags kept for existing consumers (settings diagnostics). */
  downloading: boolean;
  readyToInstall: boolean;
  installing: boolean;
  /** Open the in-app update dialog and start (or resume) the download. */
  beginUpdate: () => Promise<void>;
  /** Install the downloaded update and restart right away. */
  installNow: () => Promise<void>;
  /** Defer the installation until the next app restart. */
  installOnRestart: () => Promise<void>;
  /** Relaunch the app (from the "ready, restart pending" state). */
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

    // Never clobber an in-flight download/install or a pending restart:
    // scheduled re-checks used to wipe the "ready to install" state.
    if (state.phase !== "idle") {
      return update;
    }

    if (!update.enabled || !update.update_available) {
      setState({
        available: false,
        version: update.latest_version || null,
        notes: update.release_notes || null,
        forceUpdate: false,
        downloadUrl: update.download_url || null,
        downloadFilename: update.download_filename || null,
        downloadSha256: update.download_sha256 || null,
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

/** Download the signed update via Tauri's updater without installing it. */
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

  return true;
}

async function beginUpdate(options?: { autoInstall?: boolean }): Promise<void> {
  if (!IS_DESKTOP) return;
  const autoInstall = options?.autoInstall ?? false;

  // Resume states: never restart a download that is running or already done.
  if (state.phase === "downloading" || state.phase === "installing" || state.phase === "restart-pending") {
    setState({ dialogOpen: true });
    return;
  }
  if (state.phase === "downloaded" && pendingTauriUpdate) {
    setState({ dialogOpen: true, error: null });
    if (autoInstall) await installNow();
    return;
  }

  setState({ dialogOpen: true, phase: "downloading", progress: 0, error: null });
  try {
    const found = await downloadWithTauriUpdater();
    if (!found) {
      setState({
        phase: "idle",
        progress: 0,
        error: "未找到签名的应用内更新包，请联系管理员在后台上传 updater 包和 .sig 签名文件。",
      });
      return;
    }
    setState({ phase: "downloaded", progress: 100, error: null });
    if (autoInstall) {
      await installNow();
    }
  } catch (error) {
    console.error("Update download failed:", error);
    closePendingTauriUpdate();
    const message = error instanceof Error ? error.message : String(error);
    setState({ phase: "idle", progress: 0, error: message });
  }
}

async function installNow(): Promise<void> {
  if (state.phase !== "downloaded" && state.phase !== "installing") return;
  if (!pendingTauriUpdate) {
    setState({ phase: "idle", error: "更新包还没有下载完成，请重新下载。" });
    return;
  }
  setState({ phase: "installing", dialogOpen: true, error: null });
  try {
    const update = pendingTauriUpdate;
    // On Windows install() exits the app into the installer automatically;
    // on macOS/Linux we relaunch explicitly right after.
    await update.install();
    pendingTauriUpdate = null;
    clearPendingInstall();
    await update.close().catch(() => undefined);
    const { relaunch } = await import("@tauri-apps/plugin-process");
    await relaunch();
  } catch (error) {
    console.error("Update install failed:", error);
    const message = error instanceof Error ? error.message : String(error);
    setState({ phase: "downloaded", error: message });
  }
}

async function installOnRestart(): Promise<void> {
  if (state.phase !== "downloaded") return;
  if (!pendingTauriUpdate) {
    setState({ phase: "idle", error: "更新包还没有下载完成，请重新下载。" });
    return;
  }
  const targetVersion = pendingUpdate?.latest_version || state.version || "";
  try {
    const platform = await desktopAPI.getPlatform().catch(() => "");
    if (platform === "windows") {
      // Windows NSIS install() would close the app immediately, so defer the
      // whole install: remember the target version and finish automatically
      // on the next startup.
      savePendingInstall({ version: targetVersion });
      setState({ phase: "restart-pending", dialogOpen: false, error: null });
      return;
    }
    // macOS/Linux: installing now is safe — the running app keeps working
    // and the new version simply takes effect on the next launch.
    setState({ phase: "installing", error: null });
    const update = pendingTauriUpdate;
    await update.install();
    pendingTauriUpdate = null;
    clearPendingInstall();
    await update.close().catch(() => undefined);
    setState({ phase: "restart-pending", dialogOpen: false, error: null });
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
  if (state.phase === "restart-pending") {
    // The install is already scheduled; hide the notice and don't nag again
    // for this version until the restart applies it.
    const version = pendingUpdate?.latest_version || state.version;
    if (version) localStorage.setItem(DISMISSED_KEY, version);
    setState({ dismissed: true, available: false, dialogOpen: false, phase: "idle" });
    return;
  }
  const version = pendingUpdate?.latest_version || state.version;
  if (version) localStorage.setItem(DISMISSED_KEY, version);
  setState({ dismissed: true, available: false });
}

/** Complete a deferred ("install on next restart") update at startup. */
async function resumePendingInstall(): Promise<void> {
  const entry = readPendingInstall();
  if (!entry) return;
  // The startup check already ran; trust the server's verdict, which also
  // covers same-version package (sha256) updates.
  if (!pendingUpdate?.update_available) {
    clearPendingInstall();
    return;
  }
  clearPendingInstall();
  await beginUpdate({ autoInstall: true });
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
    downloading: snapshot.phase === "downloading",
    readyToInstall: snapshot.phase === "downloaded",
    installing: snapshot.phase === "installing",
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
