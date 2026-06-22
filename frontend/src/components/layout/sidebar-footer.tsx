"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, ImagePlus, MessageSquare, Settings } from "lucide-react";
import { useTranslation } from "react-i18next";
import Link from "next/link";
import { useUpdateCheck } from "@/hooks/use-update-check";
import { readCompanySession } from "@/lib/company-auth";
import { apiErrorMessage } from "@/lib/api";
import { enterpriseApi } from "@/lib/enterprise-api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function SidebarFooter() {
  const { t } = useTranslation(["common", "settings"]);
  const { available: updateAvailable, version: updateVersion } = useUpdateCheck();
  const [displayName, setDisplayName] = useState("员工");
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackDescription, setFeedbackDescription] = useState("");
  const [feedbackImage, setFeedbackImage] = useState<File | null>(null);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  useEffect(() => {
    const syncDisplayName = () => {
      const user = readCompanySession()?.user;
      setDisplayName(user?.display_name?.trim() || user?.email || "员工");
    };
    syncDisplayName();
    window.addEventListener("storage", syncDisplayName);
    return () => window.removeEventListener("storage", syncDisplayName);
  }, []);

  function resetFeedbackForm() {
    setFeedbackDescription("");
    setFeedbackImage(null);
    setFeedbackMessage("");
    setFeedbackSubmitted(false);
  }

  function closeFeedbackDialog() {
    setFeedbackOpen(false);
    resetFeedbackForm();
  }

  async function submitFeedback() {
    const description = feedbackDescription.trim();
    if (!description) {
      setFeedbackMessage(t("common:feedbackDescriptionRequired"));
      return;
    }

    const form = new FormData();
    form.set("description", description);
    if (feedbackImage) form.set("image", feedbackImage);

    setFeedbackSubmitting(true);
    setFeedbackMessage("");
    try {
      await enterpriseApi.postForm("/api/feedback", form, { timeoutMs: 60_000 });
      setFeedbackDescription("");
      setFeedbackImage(null);
      setFeedbackSubmitted(true);
    } catch (error) {
      setFeedbackMessage(apiErrorMessage(error, t("common:feedbackSubmitFailed")));
    } finally {
      setFeedbackSubmitting(false);
    }
  }

  return (
    <div className="space-y-1 px-3 py-2">
      <Dialog
        open={feedbackOpen}
        onOpenChange={(open) => {
          setFeedbackOpen(open);
          if (!open) resetFeedbackForm();
        }}
      >
        <DialogTrigger asChild>
          <button
            className="flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left text-ui-body text-[var(--text-secondary)] transition-colors hover:bg-[var(--sidebar-hover)] hover:text-[var(--text-primary)]"
          >
            <MessageSquare className="h-3.5 w-3.5 shrink-0" />
            <span>{t("common:feedback")}</span>
          </button>
        </DialogTrigger>
        <DialogContent className="max-w-[460px]">
          {feedbackSubmitted ? (
            <div className="space-y-5 py-2">
              <div className="grid justify-items-center gap-3 text-center">
                <CheckCircle2 className="h-10 w-10 text-[var(--brand-primary)]" />
                <div className="space-y-1">
                  <DialogTitle>{t("common:feedbackSubmittedTitle")}</DialogTitle>
                  <DialogDescription>{t("common:feedbackSubmittedDescription")}</DialogDescription>
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="border-[var(--brand-primary)] bg-white text-[var(--brand-primary)] hover:bg-white"
                  onClick={resetFeedbackForm}
                >
                  {t("common:feedbackAgain")}
                </Button>
                <Button
                  type="button"
                  className="bg-[var(--brand-primary)] text-white hover:bg-[var(--brand-primary-hover)]"
                  onClick={closeFeedbackDialog}
                >
                  {t("common:feedbackClose")}
                </Button>
              </div>
            </div>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>{t("common:feedbackTitle")}</DialogTitle>
                <DialogDescription>{t("common:feedbackDesc")}</DialogDescription>
              </DialogHeader>
              <div className="space-y-3">
                <label className="grid gap-1.5 text-ui-caption text-[var(--text-secondary)]">
                  <span>{t("common:feedbackDescription")}</span>
                  <textarea
                    className="min-h-[120px] w-full resize-y rounded-[var(--radius)] border border-[var(--border-default)] bg-transparent px-3 py-2 text-sm text-[var(--text-primary)] shadow-[var(--shadow-sm)] outline-none transition-colors placeholder:text-[var(--text-tertiary)] focus-visible:ring-1 focus-visible:ring-[var(--ring)]"
                    value={feedbackDescription}
                    onChange={(event) => setFeedbackDescription(event.target.value)}
                    placeholder={t("common:feedbackDescriptionPlaceholder")}
                  />
                </label>
                <div className="grid gap-1.5 text-ui-caption text-[var(--text-secondary)]">
                  <span>{t("common:feedbackImage")}</span>
                  <div className="flex items-center gap-2">
                    <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-[var(--radius)] border border-[var(--border-default)] px-3 text-sm text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-secondary)]">
                      <ImagePlus className="h-4 w-4" />
                      <span>{feedbackImage ? t("common:feedbackReplaceImage") : t("common:feedbackChooseImage")}</span>
                      <input
                        className="hidden"
                        type="file"
                        accept="image/*"
                        onChange={(event) => {
                          setFeedbackImage(event.currentTarget.files?.[0] ?? null);
                          event.currentTarget.value = "";
                        }}
                      />
                    </label>
                    {feedbackImage && (
                      <button
                        type="button"
                        className="truncate text-ui-caption text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                        title={feedbackImage.name}
                        onClick={() => setFeedbackImage(null)}
                      >
                        {feedbackImage.name}
                      </button>
                    )}
                  </div>
                </div>
                {feedbackMessage && (
                  <p className="break-words text-ui-caption text-[var(--text-secondary)]">
                    {feedbackMessage}
                  </p>
                )}
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={closeFeedbackDialog}
                    disabled={feedbackSubmitting}
                  >
                    {t("common:cancel")}
                  </Button>
                  <Button
                    type="button"
                    onClick={() => void submitFeedback()}
                    disabled={feedbackSubmitting}
                  >
                    {feedbackSubmitting ? t("common:feedbackSubmitting") : t("common:feedbackSubmit")}
                  </Button>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
      <Link
        href="/settings"
        className="flex items-center gap-2 rounded-lg px-2 py-1 text-ui-body text-[var(--text-secondary)] transition-colors hover:bg-[var(--sidebar-hover)] hover:text-[var(--text-primary)]"
      >
        <Settings className="h-3.5 w-3.5 shrink-0" />
        <span>{t("common:settings")}</span>
        {updateAvailable && (
          <span
            className="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--brand-primary)]"
            aria-label={t("settings:updateAvailable")}
            title={
              updateVersion
                ? `${t("settings:updateAvailable")} · v${updateVersion}`
                : t("settings:updateAvailable")
            }
          />
        )}
      </Link>
      <div
        className="truncate rounded-lg px-2 py-1 text-ui-body text-[var(--text-secondary)]"
        title={displayName}
      >
        {displayName}
      </div>
    </div>
  );
}
