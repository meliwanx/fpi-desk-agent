"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";

export interface ConversationNavItem {
  id: string;
  index: number;
  promptPreview: string;
  replyPreview: string;
}

interface ConversationNavigatorProps {
  items: ConversationNavItem[];
  activeItemId: string | null;
  onSelect: (itemId: string) => void;
}

export const ConversationNavigator = memo(function ConversationNavigator({
  items,
  activeItemId,
  onSelect,
}: ConversationNavigatorProps) {
  if (items.length === 0) return null;

  return (
    <nav
      data-testid="conversation-navigator"
      aria-label="对话节点导航"
      className="group/conversation-nav pointer-events-none absolute left-3 top-8 bottom-24 z-20 hidden w-12 lg:block"
    >
      <div className="pointer-events-auto sticky top-10 flex max-h-[calc(100vh-13rem)] items-center">
        <div className="relative flex max-h-[min(68vh,34rem)] min-h-32 w-12 items-center justify-center py-4">
          <div className="absolute left-5 top-4 bottom-4 w-px rounded-full bg-[var(--border-default)] opacity-80" />
          <div className="relative flex max-h-full flex-col justify-end gap-1.5 overflow-hidden py-1">
            {items.map((item, idx) => {
              const isActive = item.id === activeItemId;
              const distanceFromLatest = items.length - idx - 1;
              const widthClass = isActive
                ? "w-9 bg-[var(--text-primary)]"
                : distanceFromLatest % 4 === 0
                  ? "w-6 bg-[var(--text-tertiary)]"
                  : distanceFromLatest % 2 === 0
                    ? "w-4 bg-[var(--text-tertiary)]"
                    : "w-2.5 bg-[var(--text-tertiary)]";

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelect(item.id)}
                  aria-label={`跳转到第 ${item.index} 次对话`}
                  aria-current={item.id === activeItemId ? "true" : undefined}
                  title={item.promptPreview}
                  className={cn(
                    "h-0.5 rounded-full opacity-70 transition-all duration-200 ease-out hover:bg-[var(--brand-primary)] hover:opacity-100 group-hover/conversation-nav:w-9 group-hover/conversation-nav:opacity-100",
                    widthClass,
                  )}
                  style={{ transitionDelay: `${Math.min(idx, 12) * 14}ms` }}
                />
              );
            })}
          </div>
        </div>

        <div className="pointer-events-none absolute left-10 top-1/2 w-[min(22rem,calc(100vw-10rem))] -translate-y-1/2 translate-x-2 rounded-xl border border-[var(--border-default)] bg-[var(--surface-primary)]/95 p-2 opacity-0 shadow-[var(--shadow-lg)] backdrop-blur transition-all duration-200 group-hover/conversation-nav:pointer-events-auto group-hover/conversation-nav:translate-x-0 group-hover/conversation-nav:opacity-100">
          <div className="max-h-[min(64vh,32rem)] space-y-1 overflow-y-auto pr-1 scrollbar-auto">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelect(item.id)}
                aria-current={item.id === activeItemId ? "true" : undefined}
                className={cn(
                  "block w-full rounded-lg px-3 py-2 text-left transition-colors",
                  item.id === activeItemId
                    ? "bg-[var(--brand-primary)] text-[var(--brand-primary-text)]"
                    : "text-[var(--text-primary)] hover:bg-[var(--surface-secondary)]",
                )}
              >
                <div className="flex items-center gap-2 text-[11px] font-medium opacity-80">
                  <span className="h-1.5 w-1.5 rounded-full bg-current" />
                  <span>第 {item.index} 次对话</span>
                </div>
                <div className="mt-1 line-clamp-2 text-[12px] font-medium leading-relaxed">
                  {item.promptPreview}
                </div>
                {item.replyPreview && (
                  <div
                    className={cn(
                      "mt-1 line-clamp-2 text-[11px] leading-relaxed",
                      item.id === activeItemId ? "opacity-80" : "text-[var(--text-tertiary)]",
                    )}
                  >
                    {item.replyPreview}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>
    </nav>
  );
});
