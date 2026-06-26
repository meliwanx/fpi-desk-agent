import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const chatForm = readFileSync(resolve(root, "src/components/chat/chat-form.tsx"), "utf8");
const constants = readFileSync(resolve(root, "src/lib/constants.ts"), "utf8");
const voiceInput = readFileSync(resolve(root, "src/lib/voice-input.ts"), "utf8");
const zhChat = readFileSync(resolve(root, "src/i18n/locales/zh/chat.json"), "utf8");
const enChat = readFileSync(resolve(root, "src/i18n/locales/en/chat.json"), "utf8");
const recordingStopBlock = chatForm.slice(
  chatForm.indexOf("const handleRecordingStopped"),
  chatForm.indexOf("const handleVoiceButtonClick"),
);

assert.match(
  constants,
  /VOICE:\s*\{[\s\S]+TRANSCRIBE:\s*"\/api\/voice\/transcribe"/,
  "API constants should expose the voice transcription endpoint",
);
assert.match(
  voiceInput,
  /new FormData\(\)/,
  "voice helper should upload audio as multipart/form-data",
);
assert.match(
  voiceInput,
  /append\("audio",/,
  "voice helper should send the audio file using the audio field",
);
assert.match(
  voiceInput,
  /TARGET_SAMPLE_RATE\s*=\s*16000/,
  "voice helper should encode uploaded audio as 16 kHz WAV",
);
assert.match(
  chatForm,
  /navigator\.mediaDevices\.getUserMedia/,
  "chat composer should request microphone access",
);
assert.match(
  chatForm,
  /new MediaRecorder/,
  "chat composer should record microphone audio",
);
assert.match(
  chatForm,
  /transcribeVoiceInput\(/,
  "chat composer should call the voice transcription helper",
);
assert.match(
  chatForm,
  /insertVoiceTextIntoInput/,
  "voice result should be inserted into the composer input",
);
assert.doesNotMatch(
  recordingStopBlock,
  /onSend\(/,
  "voice transcription should not automatically send the message",
);
assert.match(zhChat, /"voiceStart": "语音输入"/, "Chinese chat copy should include voice start label");
assert.match(enChat, /"voiceStart": "Voice input"/, "English chat copy should include voice start label");
