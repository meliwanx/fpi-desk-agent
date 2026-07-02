"use client";

import { useState } from "react";
import { CheckCircle2, Download, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { useUpdateCheck } from "@/hooks/use-update-check";
import { Button } from "@/components/ui/button";

export function UpdateBanner() {
  const { t } = useTranslation("settings");
  const [showNotes, setShowNotes] = useState(false);
  const {
    available,
    version,
    notes,
    forceUpdate,
    phase,
    dialogOpen,
    progress,
    error,
    beginUpdate,
    relaunchNow,
    dismiss,
  } = useUpdateCheck();

  const busy = phase === "downloading" || phase === "installing";
  const restartPending = phase === "restart-pending";
  const showForceGate = available && forceUpdate && !dialogOpen && !restartPending;
  // The floating reminder only shows while the update dialog is closed;
  // the restart-pending notice is shown even after the update was dismissed.
  const showReminder = !forceUpdate && !dialogOpen && (restartPending || available);

  return (
    <AnimatePresence>
      {showForceGate && (
        <motion.div
          className="fixed inset-0 z-[1000] grid place-items-center bg-black/35 px-6 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="w-full max-w-[460px] rounded-2xl border border-[var(--border-default)] bg-[var(--surface-primary)] p-6 shadow-[var(--shadow-lg)]">
            <div className="mb-4 flex items-center gap-2 text-[var(--brand-primary)]">
              <Download className="h-4 w-4" />
              <span className="text-ui-caption font-semibold">{t("updateRequired")}</span>
            </div>
            <h2 className="text-ui-title-sm font-semibold text-[var(--text-primary)]">
              {t("updateRequiredTitle", { version })}
            </h2>
            {notes && (
              <p className="mt-3 whitespace-pre-wrap text-ui-caption leading-6 text-[var(--text-secondary)]">
                {notes}
              </p>
            )}
            {error && (
              <p className="mt-3 break-all text-ui-caption text-[var(--color-destructive)]">
                {t("updateFailed")}: {error}
              </p>
            )}
            <Button
              className="mt-5 w-full"
              onClick={() => void beginUpdate()}
              disabled={busy}
            >
              {busy ? t("updateDownloading") : t("updateDownload")}
            </Button>
            <p className="mt-3 text-center text-ui-3xs text-[var(--text-tertiary)]">
              {t("updateRequiredDesc")}
            </p>
          </div>
        </motion.div>
      )}
      {showReminder && (
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 18 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="fixed bottom-4 left-4 z-[900] w-[min(360px,calc(100vw-32px))]"
        >
          <div className="rounded-xl border border-[var(--border-default)] bg-[var(--surface-primary)] p-4 shadow-[var(--shadow-lg)]">
            {restartPending ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 rounded-full bg-green-500/10 p-1 text-green-500">
                      <CheckCircle2 className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="text-ui-caption font-semibold text-[var(--text-primary)]">
                        {t("updateScheduledTitle")}
                      </p>
                      <p className="mt-1 text-ui-caption text-[var(--text-secondary)]">
                        {t("updateScheduledDesc")}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={dismiss}
                    className="rounded p-1 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-secondary)] hover:text-[var(--text-primary)]"
                    aria-label={t("updateLater")}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <Button size="sm" className="h-8 w-full text-ui-caption" onClick={() => void relaunchNow()}>
                  {t("updateRelaunchNow")}
                </Button>
              </div>
            ) : error && !busy && !dialogOpen ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="break-all text-ui-caption text-[var(--color-destructive)]">
                    {t("updateFailed")}: {error}
                  </p>
                  <button
                    onClick={dismiss}
                    className="rounded p-1 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-secondary)] hover:text-[var(--text-primary)]"
                    aria-label={t("updateLater")}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <Button size="sm" className="h-8 w-full text-ui-caption" onClick={() => void beginUpdate()}>
                  {t("updateRetry")}
                </Button>
              </div>
            ) : busy && !dialogOpen ? (
              <button className="w-full space-y-3 text-left" onClick={() => void beginUpdate()}>
                <div className="flex items-center gap-2 text-ui-caption font-semibold text-[var(--brand-primary)]">
                  <Download className="h-4 w-4" />
                  <span>{t("updateDownloading")} {progress}%</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--brand-primary)]/15">
                  <div
                    className="h-full rounded-full bg-[var(--brand-primary)] transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </button>
            ) : phase === "idle" && !dialogOpen ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 rounded-full bg-[var(--brand-primary)]/10 p-1 text-[var(--brand-primary)]">
                      <Download className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="text-ui-caption font-semibold text-[var(--text-primary)]">
                        {t("updateAvailable")}
                      </p>
                      <p className="mt-1 text-ui-caption text-[var(--text-secondary)]">
                        {t("updateAvailableDesc", { version })}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={dismiss}
                    className="rounded p-1 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-secondary)] hover:text-[var(--text-primary)]"
                    aria-label={t("updateLater")}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                {showNotes && notes && (
                  <p className="max-h-28 overflow-auto whitespace-pre-wrap rounded-lg bg-[var(--surface-secondary)] p-3 text-ui-caption leading-5 text-[var(--text-secondary)]">
                    {notes}
                  </p>
                )}
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 flex-1 text-ui-caption"
                    onClick={() => setShowNotes((value) => !value)}
                    disabled={!notes}
                  >
                    {t("updateReleaseNotes")}
                  </Button>
                  <Button size="sm" className="h-8 flex-1 text-ui-caption" onClick={() => void beginUpdate()}>
                    {t("updateNow")}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
