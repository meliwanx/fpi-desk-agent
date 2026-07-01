import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const workspaceStore = readFileSync(resolve(root, "src/stores/workspace-store.ts"), "utf8");
const streamRegistry = readFileSync(resolve(root, "src/lib/session-stream-registry.ts"), "utf8");
const chatView = readFileSync(resolve(root, "src/components/chat/chat-view.tsx"), "utf8");
const useChat = readFileSync(resolve(root, "src/hooks/use-chat.ts"), "utf8");
const messageContent = readFileSync(resolve(root, "src/components/messages/message-content.tsx"), "utf8");
const assistantMessage = readFileSync(resolve(root, "src/components/messages/assistant-message.tsx"), "utf8");
const activitySummary = readFileSync(resolve(root, "src/components/activity/activity-summary.tsx"), "utf8");

assert.match(
  workspaceStore,
  /activeSessionId:\s*string \| null/,
  "workspace progress state should be scoped to the active chat session",
);
assert.match(
  workspaceStore,
  /workspaceBySession/,
  "workspace store should retain per-session progress snapshots when switching chats",
);
assert.match(
  chatView,
  /resetForSession\(sessionId\)/,
  "chat view should load the workspace snapshot for the selected session",
);
assert.match(
  streamRegistry,
  /setTodos\(meta\.todos as WorkspaceTodo\[\], sessionId\)/,
  "todo updates from SSE should be written to the originating session only",
);
assert.match(
  streamRegistry,
  /setTaskBatch\(\{[\s\S]+?\}, sessionId\)/,
  "task-batch updates from SSE should be written to the originating session only",
);
assert.match(
  streamRegistry,
  /focusedSessionId === sessionId[\s\S]+openArtifact/,
  "artifact panels should only auto-open for the currently focused session",
);
assert.match(
  streamRegistry,
  /focusedSessionId === sessionId[\s\S]+openReview/,
  "plan review panels should only auto-open for the currently focused session",
);
assert.match(
  streamRegistry,
  /workspace\.activeSessionId === sid[\s\S]+collapseSection\("progress"\)/,
  "finished background streams should not collapse the current session's workspace progress",
);
assert.match(
  useChat,
  /setTodos\(\[\], currentSessionId\)/,
  "edit-and-resend should clear progress only for the edited session",
);

assert.match(
  assistantMessage,
  /activityKey=\{sessionId \? `stream:\$\{sessionId\}` : undefined\}/,
  "streaming messages should expose a stable live activity key",
);
assert.match(
  messageContent,
  /isStreaming && activityData && activityKey[\s\S]+refreshForMessage\(activityKey, activityData\)/,
  "live activity panel data should refresh while a response is streaming",
);
assert.match(
  messageContent,
  /activityData && <ActivitySummary data=\{activityData\}/,
  "the execution summary should remain visible during streaming and after completion",
);
assert.match(
  activitySummary,
  /Loader2/,
  "activity summary should show an explicit running state",
);
assert.match(
  activitySummary,
  /stageWorkingWithTools/,
  "activity summary should label active tool execution clearly",
);
