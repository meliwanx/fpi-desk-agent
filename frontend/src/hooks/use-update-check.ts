"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { API, IS_DESKTOP } from "@/lib/constants";
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
  download_url: string;
  download_filename?: string;
  download_size_bytes?: number;
  checked_at: string;
}

interface UpdateState {
  available: boolean;
  version: string | null;
  notes: string | null;
  forceUpdate: boolean;
  downloadUrl: string | null;
  downloadFilename: string | null;
  downloading: boolean;
  progress: number;
  dismissed: boolean;
  error: string | null;
}

interface UpdateInfo extends Omit<UpdateState, "dismissed"> {
  downloadAndInstall: () => Promise<void>;
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
  downloading: false,
  progress: 0,
  dismissed: false,
  error: null,
};

const listeners = new Set<() => void>();
let pendingUpdate: EnterpriseUpdatePolicy | null = null;
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
        downloading: false,
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

function fallbackUpdateFilename(downloadUrl: string, version: string | null): string {
  try {
    const segment = decodeURIComponent(new URL(downloadUrl).pathname.split("/").pop() || "");
    if (segment.includes(".")) return segment;
  } catch {
    // Fall through to version-based name.
  }
  return `fpi-agent-${version || "update"}.bin`;
}

async function downloadAndInstall() {
  const downloadUrl = pendingUpdate?.download_url || state.downloadUrl;
  if (!downloadUrl) {
    setState({ error: "未配置下载地址", downloading: false });
    return;
  }
  const defaultName =
    pendingUpdate?.download_filename ||
    state.downloadFilename ||
    fallbackUpdateFilename(downloadUrl, pendingUpdate?.latest_version || state.version);
  setState({ downloading: true, error: null, progress: 0 });
  try {
    await desktopAPI.downloadUpdateAndOpen({ url: downloadUrl, defaultName });
    setState({ downloading: false, progress: 100 });
  } catch (error) {
    console.error("Update download failed:", error);
    const message = error instanceof Error ? error.message : String(error);
    setState({ error: message, downloading: false });
  }
}

function dismiss() {
  if (state.forceUpdate) return;
  if (state.version) localStorage.setItem(DISMISSED_KEY, state.version);
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
  downloading: false,
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
  const boundDownload = useCallback(() => downloadAndInstall(), []);
  const boundDismiss = useCallback(() => dismiss(), []);
  const boundCheck = useCallback(() => checkForUpdates(), []);

  return {
    available: snapshot.available && !snapshot.dismissed,
    version: snapshot.version,
    notes: snapshot.notes,
    forceUpdate: snapshot.forceUpdate,
    downloadUrl: snapshot.downloadUrl,
    downloadFilename: snapshot.downloadFilename,
    downloading: snapshot.downloading,
    progress: snapshot.progress,
    error: snapshot.error,
    downloadAndInstall: boundDownload,
    dismiss: boundDismiss,
    checkNow: boundCheck,
  };
}
