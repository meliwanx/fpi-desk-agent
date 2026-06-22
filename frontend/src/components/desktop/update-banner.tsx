"use client";

import { Download, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { useUpdateCheck } from "@/hooks/use-update-check";
import { Button } from "@/components/ui/button";

export function UpdateBanner() {
  const { t } = useTranslation("settings");
  const {
    available,
    version,
    notes,
    forceUpdate,
    downloading,
    progress,
    error,
    downloadAndInstall,
    dismiss,
  } = useUpdateCheck();

  return (
    <AnimatePresence>
      {available && forceUpdate && (
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
              onClick={downloadAndInstall}
              disabled={downloading}
            >
              {downloading ? t("updateOpening") : t("updateDownload")}
            </Button>
            <p className="mt-3 text-center text-ui-3xs text-[var(--text-tertiary)]">
              {t("updateRequiredDesc")}
            </p>
          </div>
        </motion.div>
      )}
      {available && !forceUpdate && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeInOut" }}
          className="overflow-hidden"
        >
          <div className="flex items-center justify-center gap-3 px-4 py-1.5 text-xs font-medium bg-[var(--brand-primary)]/10 text-[var(--brand-primary)]">
            {error ? (
              <>
                <span className="text-[var(--color-destructive)]">{t("updateFailed")}: {error}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-5 px-2 text-xs font-semibold text-[var(--brand-primary)] hover:bg-[var(--brand-primary)]/20"
                  onClick={downloadAndInstall}
                >
                  {t("updateRetry")}
                </Button>
                <button
                  onClick={dismiss}
                  className="ml-1 rounded p-0.5 hover:bg-[var(--brand-primary)]/20 transition-colors"
                  aria-label={t("updateLater")}
                >
                  <X className="h-3 w-3" />
                </button>
              </>
            ) : downloading ? (
              <>
                <div className="flex items-center gap-2">
                  <div className="h-1 w-24 rounded-full bg-[var(--brand-primary)]/20 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[var(--brand-primary)] transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <span>{t("updateDownloading")} {progress}%</span>
                </div>
              </>
            ) : (
              <>
                <Download className="h-3 w-3" />
                <span>{t("updateAvailableDesc", { version })}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-5 px-2 text-xs font-semibold text-[var(--brand-primary)] hover:bg-[var(--brand-primary)]/20"
                  onClick={downloadAndInstall}
                >
                  {t("updateNow")}
                </Button>
                <button
                  onClick={dismiss}
                  className="ml-1 rounded p-0.5 hover:bg-[var(--brand-primary)]/20 transition-colors"
                  aria-label={t("updateLater")}
                >
                  <X className="h-3 w-3" />
                </button>
              </>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
