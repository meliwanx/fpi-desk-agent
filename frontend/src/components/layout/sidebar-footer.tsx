"use client";

import { useEffect, useState } from "react";
import { Settings } from "lucide-react";
import { useTranslation } from "react-i18next";
import Link from "next/link";
import { useUpdateCheck } from "@/hooks/use-update-check";
import { readCompanySession } from "@/lib/company-auth";

export function SidebarFooter() {
  const { t } = useTranslation(["common", "settings"]);
  const { available: updateAvailable, version: updateVersion } = useUpdateCheck();
  const [displayName, setDisplayName] = useState("员工");

  useEffect(() => {
    const syncDisplayName = () => {
      const user = readCompanySession()?.user;
      setDisplayName(user?.display_name?.trim() || user?.email || "员工");
    };
    syncDisplayName();
    window.addEventListener("storage", syncDisplayName);
    return () => window.removeEventListener("storage", syncDisplayName);
  }, []);

  return (
    <div className="space-y-1 px-3 py-2">
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
