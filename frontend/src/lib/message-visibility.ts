import type { MessageResponse, PartData } from "@/types/message";

const INTERNAL_PART_TYPES = new Set(["step-start", "step-finish"]);

export function partHasVisibleChatContent(part: PartData): boolean {
  if (INTERNAL_PART_TYPES.has(part.type)) return false;
  if (part.type === "text" || part.type === "reasoning") {
    return Boolean(part.text.trim());
  }
  return true;
}

export function chatMessageIsVisible(message: MessageResponse): boolean {
  const data = message.data as unknown as Record<string, unknown>;
  if (data.system === true) return false;
  if (data.role !== "assistant") return true;

  if (typeof data.error === "string" && data.error.trim()) return true;
  return message.parts.some((part) => partHasVisibleChatContent(part.data as PartData));
}

export function latestVisibleAssistantMessage(
  messages: MessageResponse[],
): MessageResponse | undefined {
  return [...messages]
    .reverse()
    .find((message) => message.data.role === "assistant" && chatMessageIsVisible(message));
}
