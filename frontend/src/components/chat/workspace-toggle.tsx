"use client";

import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { FolderOpen } from "lucide-react";
import { Loader2 } from "lucide-react";
import { useSettingsStore } from "@/stores/settings-store";
import { toast } from "sonner";
import { browseDirectory } from "@/lib/upload";
import { isRemoteMode } from "@/lib/remote-connection";
import { MobileDirectoryBrowser } from "@/components/mobile/directory-browser";

interface WorkspaceToggleProps {
  /** When provided, workspace changes are persisted to this session via PATCH. */
  sessionId?: string;
  /** The session's current directory (used when sessionId is provided). */
  directory?: string | null;
  /** Whether the workspace is currently being indexed. Shows spinner when true. */
  isIndexing?: boolean;
}

function getDisplayName(path: string | null | undefined): string | null {
  if (!path || path === ".") return null;
  const normalized = path.replace(/\\/g, "/").replace(/\/$/, "");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || null;
}

export function WorkspaceToggle({ sessionId, directory, isIndexing }: WorkspaceToggleProps) {
  const { t } = useTranslation("chat");
  const [browsingDirs, setBrowsingDirs] = useState(false);
  const remote = isRemoteMode();
  const isLocked = !!sessionId;

  // For new chats (no sessionId), use global settings store
  const globalWorkspace = useSettingsStore((s) => s.workspaceDirectory);
  const setGlobalWorkspace = useSettingsStore((s) => s.setWorkspaceDirectory);

  // Resolved values depending on context
  const currentPath = sessionId ? directory : globalWorkspace;
  const displayName = getDisplayName(currentPath);
  const pillLabel = displayName ?? t("workspaceNone");

  // Existing sessions keep their original workspace. New chats can pick a folder
  // before the first message creates the session.
  const applySelectedPath = useCallback(async (path: string) => {
    if (isLocked) {
      toast.info(t("workspaceLocked"));
      return;
    }
    setGlobalWorkspace(path);
  }, [isLocked, setGlobalWorkspace, t]);

  const handleBrowse = useCallback(async () => {
    if (isLocked) {
      toast.info(t("workspaceLocked"));
      return;
    }
    if (remote) {
      // Remote mode: use directory browser instead of native OS dialog
      setBrowsingDirs(true);
      return;
    }
    try {
      const path = await browseDirectory(t("workspaceSet"));
      if (path) {
        await applySelectedPath(path);
      }
    } catch (err) {
      console.error("Failed to browse directory:", err);
      toast.error(t("workspaceBrowseFailed"));
    }
  }, [isLocked, remote, t, applySelectedPath]);

  return (
    <>
      {displayName ? (
        <button
          type="button"
          onClick={handleBrowse}
          className="inline-flex max-w-[220px] items-center gap-1.5 rounded-full bg-[var(--surface-tertiary)] py-1.5 pl-3 pr-3 text-[13px] text-[var(--text-primary)]"
          title={currentPath ?? undefined}
        >
          {isIndexing ? (
            <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
          ) : (
            <FolderOpen className="h-4 w-4 shrink-0" />
          )}
          <span className="truncate">{pillLabel}</span>
          {isIndexing && (
            <span className="shrink-0 text-[11px] text-[var(--text-tertiary)]">{t("workspaceIndexing")}</span>
          )}
        </button>
      ) : (
        <button
          type="button"
          onClick={handleBrowse}
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] transition-colors max-w-[220px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--surface-tertiary)]"
        >
          <FolderOpen className="h-4 w-4 shrink-0" />
          <span className="truncate">{pillLabel}</span>
        </button>
      )}
      {remote && (
        <MobileDirectoryBrowser
          open={browsingDirs}
          onClose={() => setBrowsingDirs(false)}
          onSelect={(path) => void applySelectedPath(path)}
          initialPath={currentPath}
        />
      )}
    </>
  );
}
