import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const visibility = readFileSync(resolve(root, "src/lib/message-visibility.ts"), "utf8");
const messageList = readFileSync(resolve(root, "src/components/messages/message-list.tsx"), "utf8");
const streamRegistry = readFileSync(resolve(root, "src/lib/session-stream-registry.ts"), "utf8");
const chatView = readFileSync(resolve(root, "src/components/chat/chat-view.tsx"), "utf8");

assert.match(
  visibility,
  /INTERNAL_PART_TYPES\s*=\s*new Set\(\["step-start", "step-finish"\]\)/,
  "chat visibility should treat step markers as internal-only parts",
);
assert.match(
  visibility,
  /data\.system === true/,
  "system-injected messages should be hidden from the chat transcript",
);
assert.match(
  visibility,
  /partHasVisibleChatContent/,
  "chat visibility helper should expose part-level visible content checks",
);
assert.match(
  messageList,
  /if \(!chatMessageIsVisible\(msg\)\)/,
  "message grouping should drop hidden/internal messages before rendering",
);
assert.match(
  messageList,
  /streamingParts\.some\(partHasVisibleChatContent\)/,
  "streaming replacement detection should ignore internal step markers",
);
assert.match(
  streamRegistry,
  /latestVisibleAssistantMessage\(/,
  "stream finalization should use the latest visible assistant message",
);
assert.match(
  chatView,
  /latestVisibleAssistantMessage\(messages\)/,
  "copy-last should ignore internal assistant messages",
);
