import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const useChat = readFileSync(
  new URL("../../src/hooks/use-chat.ts", import.meta.url),
  "utf8",
);
const sessionItem = readFileSync(
  new URL("../../src/components/layout/session-item.tsx", import.meta.url),
  "utf8",
);
const prompt = readFileSync(
  new URL("../../../backend/app/session/prompt.py", import.meta.url),
  "utf8",
);
const titlePrompt = readFileSync(
  new URL("../../../backend/app/agent/prompts/title.txt", import.meta.url),
  "utf8",
);

assert.doesNotMatch(
  useChat,
  /title:\s*text\.trim\(\)\.slice\(0,\s*60\)/,
  "optimistic new chat title should not use the user's first long message",
);
assert.match(
  useChat,
  /title:\s*null,/,
  "optimistic new chat title should stay generic until the AI summary title arrives",
);

assert.match(
  prompt,
  /async def _generate_first_turn_title/,
  "session prompt should generate first-turn titles through a dedicated helper",
);
assert.match(
  prompt,
  /self\.agent_registry\.get\("title"\)/,
  "title generation should use the hidden title agent",
);
assert.match(
  prompt,
  /provider\.stream_chat\(/,
  "title generation should call the model instead of slicing the prompt directly",
);
assert.match(
  prompt,
  /MAX_SESSION_TITLE_CHARS\s*=\s*15/,
  "generated session titles should be capped at 15 characters",
);
assert.doesNotMatch(
  prompt,
  /title\s*=\s*self\.first_user_text\.strip\(\)\[:60\]/,
  "first-turn title should not be copied directly from the first user message",
);
assert.match(titlePrompt, /15\s*个字以内/, "title agent prompt should explicitly cap titles to 15 Chinese characters");

assert.match(sessionItem, /onDoubleClick=\{startRename\}/, "session item should allow double-click rename");
assert.match(sessionItem, /Pencil/, "session item should expose a visible rename icon");
assert.match(sessionItem, /aria-label=\{t\('rename'\)\}/, "rename button should have an accessible label");
