"use client";

import { CheckCircle2, Download, Loader2, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useUpdateCheck } from "@/hooks/use-update-check";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * In-app update dialog: shows download progress, then lets the user choose
 * between installing right away (restarts the app) or on the next restart —
 * useful when a chat/task is still running.
 */
export function UpdateDialog() {
  const { t } = useTranslation("settings");
  const {
    version,
    forceUpdate,
    phase,
    dialogOpen,
    progress,
    error,
    beginUpdate,
    installNow,
    installOnRestart,
    relaunchNow,
    closeDialog,
  } = useUpdateCheck();

  const locked = forceUpdate || phase === "installing";

  return (
    <Dialog
      open={dialogOpen}
      onOpenChange={(open) => {
        if (!open && !locked) closeDialog();
      }}
    >
      <DialogContent
        className="max-w-[420px]"
        onPointerDownOutside={(event) => {
          if (locked) event.preventDefault();
        }}
        onEscapeKeyDown={(event) => {
          if (locked) event.preventDefault();
        }}
      >
        {phase === "downloading" && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Download className="h-4 w-4 text-[var(--brand-primary)]" />
                {t("updateDialogDownloadingTitle", { version })}
              </DialogTitle>
              <DialogDescription>{t("updateDialogDownloadingDesc")}</DialogDescription>
            </DialogHeader>
            <div className="mt-2 flex items-center gap-3">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surface-secondary)]">
                <div
                  className="h-full rounded-full bg-[var(--brand-primary)] transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <span className="w-10 shrink-0 text-right text-ui-caption tabular-nums text-[var(--text-secondary)]">
                {progress}%
              </span>
            </div>
          </>
        )}

        {phase === "downloaded" && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                {t("updateReadyTitle", { version })}
              </DialogTitle>
              <DialogDescription>
                {forceUpdate ? t("updateRequiredDesc") : t("updateReadyDesc")}
              </DialogDescription>
            </DialogHeader>
            {error && (
              <p className="break-all text-ui-caption text-[var(--color-destructive)]">
                {t("updateFailed")}: {error}
              </p>
            )}
            <div className="mt-2 flex flex-col gap-2">
              <Button onClick={() => void installNow()}>
                {t("updateInstallNow")}
              </Button>
              {!forceUpdate && (
                <Button variant="outline" onClick={() => void installOnRestart()}>
                  {t("updateInstallLater")}
                </Button>
              )}
            </div>
          </>
        )}

        {phase === "installing" && (
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-[var(--brand-primary)]" />
              {t("updateInstalling")}
            </DialogTitle>
            <DialogDescription>{t("updateInstallingDesc")}</DialogDescription>
          </DialogHeader>
        )}

        {phase === "restart-pending" && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                {t("updateScheduledTitle")}
              </DialogTitle>
              <DialogDescription>{t("updateScheduledDesc")}</DialogDescription>
            </DialogHeader>
            <div className="mt-2 flex flex-col gap-2">
              <Button onClick={() => void relaunchNow()}>
                {t("updateRelaunchNow")}
              </Button>
              <Button variant="outline" onClick={closeDialog}>
                {t("updateScheduledLater")}
              </Button>
            </div>
          </>
        )}

        {phase === "idle" && (
          <>
            <DialogHeader>
              <DialogTitle>{t("updateFailed")}</DialogTitle>
              <DialogDescription className="break-all">
                {error || t("updateDialogDownloadingDesc")}
              </DialogDescription>
            </DialogHeader>
            <div className="mt-2 flex flex-col gap-2">
              <Button onClick={() => void beginUpdate()}>
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                {t("updateRetry")}
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
