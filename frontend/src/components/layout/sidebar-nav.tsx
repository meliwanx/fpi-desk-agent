"use client";

import type { ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { Clock3, Plug, Search, SquarePen } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSidebarStore } from "@/stores/sidebar-store";

export function SidebarNav() {
  const { t } = useTranslation("common");
  const router = useRouter();
  const pathname = usePathname();
  const setSearchModalOpen = useSidebarStore((s) => s.setSearchModalOpen);
  const setMobileOpen = useSidebarStore((s) => s.setOpen);

  const startNewChat = () => {
    router.push("/c/new");
    setMobileOpen(false);
  };

  const openSearch = () => {
    setSearchModalOpen(true);
    setMobileOpen(false);
  };

  return (
    <nav className="px-3 pb-5" aria-label={t("primaryNavigation")}>
      <div className="space-y-1">
        <SidebarNavButton
          icon={<SquarePen className="h-4 w-4" />}
          label={t("newChat")}
          onClick={startNewChat}
        />
        <SidebarNavButton
          icon={<Search className="h-4 w-4" />}
          label={t("searchChats")}
          onClick={openSearch}
        />
        <SidebarNavButton
          icon={<Plug className="h-4 w-4" />}
          label={t("plugins")}
          active={pathname === "/plugins"}
          onClick={() => {
            router.push("/plugins");
            setMobileOpen(false);
          }}
        />
        <SidebarNavButton
          icon={<Clock3 className="h-4 w-4" />}
          label={t("automations")}
          active={pathname === "/automations"}
          onClick={() => {
            router.push("/automations");
            setMobileOpen(false);
          }}
        />
      </div>
    </nav>
  );
}

function SidebarNavButton({
  icon,
  label,
  active = false,
  disabled = false,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "flex h-9 w-full items-center gap-3 rounded-lg px-3 text-left text-sm font-medium transition-colors",
        active
          ? "bg-[var(--sidebar-active)] text-[var(--text-primary)] shadow-[var(--sidebar-active-shadow)]"
          : "text-[var(--text-secondary)] hover:bg-[var(--sidebar-hover)] hover:text-[var(--text-primary)]",
        disabled && "cursor-default opacity-60",
      )}
    >
      <span className="flex h-4 w-4 shrink-0 items-center justify-center text-[var(--text-tertiary)]">
        {icon}
      </span>
      <span className="truncate">{label}</span>
    </button>
  );
}
