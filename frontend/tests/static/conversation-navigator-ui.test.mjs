import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const messageList = readFileSync(
  new URL("../../src/components/messages/message-list.tsx", import.meta.url),
  "utf8",
);
const navigatorUrl = new URL("../../src/components/messages/conversation-navigator.tsx", import.meta.url);
const navigatorExists = existsSync(navigatorUrl);
const navigator = navigatorExists ? readFileSync(navigatorUrl, "utf8") : "";
const chatView = readFileSync(
  new URL("../../src/components/chat/chat-view.tsx", import.meta.url),
  "utf8",
);

assert.equal(navigatorExists, true, "conversation navigator component should exist");

assert.match(
  messageList,
  /ConversationNavigator/,
  "message list should render the left conversation navigator",
);
assert.match(
  messageList,
  /buildConversationNavItems\(groups\)/,
  "message list should build navigator nodes from grouped chat turns",
);
assert.match(
  messageList,
  /scrollIntoView\(\{\s*behavior:\s*"smooth",\s*block:\s*"start"/,
  "clicking a navigator node should scroll the current message list to that turn",
);
assert.match(
  messageList,
  /data-conversation-node-id=\{group\.message\.id\}/,
  "each user-started turn should expose a stable scroll anchor",
);

assert.match(
  navigator,
  /data-testid="conversation-navigator"/,
  "navigator should expose a stable test id",
);
assert.match(
  navigator,
  /group-hover\/conversation-nav/,
  "navigator should expand its previous-turn panel on hover",
);
assert.match(
  navigator,
  /aria-current=\{item\.id === activeItemId \? "true" : undefined\}/,
  "navigator should mark the current/latest conversation node",
);
assert.match(
  navigator,
  /item\.replyPreview/,
  "navigator nodes should include assistant reply preview content",
);

assert.doesNotMatch(
  chatView,
  /Auto-fix sessions with default title[\s\S]+text\.trim\(\)\.slice\(0,\s*60\)/,
  "chat view must not overwrite AI-generated titles with the first user message",
);
