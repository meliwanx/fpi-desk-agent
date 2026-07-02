"use client";

import { Megaphone } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { useAnnouncement } from "@/hooks/use-announcement";

export function AnnouncementBanner() {
  const { announcement, markAnnouncementRead, isMarkingRead } = useAnnouncement();

  return (
    <AnimatePresence initial={false}>
      {announcement && (
        <motion.div
          key={announcement.id}
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="shrink-0 border-b border-[var(--border-subtle)] bg-[var(--surface-primary)]"
        >
          <div className="mx-auto flex w-full max-w-[1120px] items-start gap-3 px-5 py-3">
            <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[var(--brand-primary)]/10 text-[var(--brand-primary)]">
              <Megaphone className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-ui-caption font-semibold text-[var(--text-primary)]">
                通知公告
              </p>
              <p className="mt-1 whitespace-pre-wrap break-words text-ui-caption leading-5 text-[var(--text-secondary)]">
                {announcement.content}
              </p>
            </div>
            <Button
              size="sm"
              className="h-8 shrink-0 text-ui-caption"
              onClick={() => void markAnnouncementRead(announcement.id)}
              disabled={isMarkingRead}
            >
              {isMarkingRead ? "确认中..." : "我已阅读"}
            </Button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
