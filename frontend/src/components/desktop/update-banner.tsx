"use client";

import { useState } from "react";
import { Download, X } from "lucide-react";
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
    downloading,
    readyToInstall,
    installing,
    progress,
    error,
    downloadUpdate,
    installNow,
    installLater,
    dismiss,
  } = useUpdateCheck();

  return (
    <AnimatePresence>
      {available && forceUpdate && readyToInstall && (
        <motion.div
          className="fixed inset-0 z-[1000] grid place-items-center bg-black/35 px-6 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="w-full max-w-[460px] rounded-2xl border border-[var(--border-default)] bg-[var(--surface-primary)] p-6 shadow-[var(--shadow-lg)]">
            <div className="mb-4 flex items-center gap-2 text-[var(--brand-primary)]">
              <Download className="h-4 w-4" />
              <span className="text-ui-caption font-semibold">
                {forceUpdate ? t("updateRequired") : t("updateAvailable")}
              </span>
            </div>
            <h2 className="text-ui-title-sm font-semibold text-[var(--text-primary)]">
              {t("updateReadyTitle", { version })}
            </h2>
            <p className="mt-3 text-ui-caption leading-6 text-[var(--text-secondary)]">
              {t("updateReadyDesc")}
            </p>
            {error && (
              <p className="mt-3 break-all text-ui-caption text-[var(--color-destructive)]">
                {t("updateFailed")}: {error}
              </p>
            )}
            <div className="mt-5 flex flex-col gap-2 sm:flex-row">
              <Button className="h-10 flex-1" onClick={installNow} disabled={installing}>
                {installing ? t("updateInstalling") : t("updateInstallNow")}
              </Button>
              <Button
                variant="outline"
                className="h-10 flex-1"
                onClick={installLater}
                disabled={installing}
              >
                {t("updateInstallLater")}
              </Button>
            </div>
          </div>
        </motion.div>
      )}
      {available && forceUpdate && !readyToInstall && (
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
              onClick={downloadUpdate}
              disabled={downloading}
            >
              {downloading ? `${t("updateDownloading")} ${progress}%` : t("updateDownload")}
            </Button>
            {downloading && (
              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-[var(--brand-primary)]/15">
                <div
                  className="h-full rounded-full bg-[var(--brand-primary)] transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            )}
            <p className="mt-3 text-center text-ui-3xs text-[var(--text-tertiary)]">
              {t("updateRequiredDesc")}
            </p>
          </div>
        </motion.div>
      )}
      {available && !forceUpdate && (
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 18 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="fixed bottom-4 left-4 z-[900] w-[min(360px,calc(100vw-32px))]"
        >
          <div className="rounded-xl border border-[var(--border-default)] bg-[var(--surface-primary)] p-4 shadow-[var(--shadow-lg)]">
            {error ? (
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
                <Button size="sm" className="h-8 w-full text-ui-caption" onClick={downloadUpdate}>
                  {t("updateRetry")}
                </Button>
              </div>
            ) : readyToInstall ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 rounded-full bg-[var(--brand-primary)]/10 p-1 text-[var(--brand-primary)]">
                      <Download className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="text-ui-caption font-semibold text-[var(--text-primary)]">
                        {t("updateReadyTitle", { version })}
                      </p>
                      <p className="mt-1 text-ui-caption text-[var(--text-secondary)]">
                        {t("updateReadyDesc")}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={installLater}
                    className="rounded p-1 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-secondary)] hover:text-[var(--text-primary)]"
                    aria-label={t("updateInstallLater")}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 flex-1 text-ui-caption"
                    onClick={installLater}
                    disabled={installing}
                  >
                    {t("updateInstallLater")}
                  </Button>
                  <Button
                    size="sm"
                    className="h-8 flex-1 text-ui-caption"
                    onClick={installNow}
                    disabled={installing}
                  >
                    {installing ? t("updateInstalling") : t("updateInstallNow")}
                  </Button>
                </div>
              </div>
            ) : downloading ? (
              <div className="space-y-3">
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
              </div>
            ) : (
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
                  <Button size="sm" className="h-8 flex-1 text-ui-caption" onClick={downloadUpdate}>
                    {t("updateDownload")}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
