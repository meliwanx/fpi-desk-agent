import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "../..");

const layout = fs.readFileSync(
  path.join(repoRoot, "src/app/(main)/layout.tsx"),
  "utf8",
);
const landing = fs.readFileSync(
  path.join(repoRoot, "src/components/chat/landing.tsx"),
  "utf8",
);
const chatForm = fs.readFileSync(
  path.join(repoRoot, "src/components/chat/chat-form.tsx"),
  "utf8",
);
const providerModels = fs.readFileSync(
  path.join(repoRoot, "src/hooks/use-provider-models.ts"),
  "utf8",
);

assert.doesNotMatch(
  layout,
  /OnboardingScreen|needsOnboarding|hasCompletedOnboarding/,
  "main desktop layout should not block first run behind onboarding",
);

assert.doesNotMatch(
  landing,
  /setupProvider|configureSettings|settings\?tab=providers|activeProvider/,
  "chat landing should not show local provider setup guidance",
);

assert.doesNotMatch(
  chatForm,
  /isInputDisabled\s*=\s*[^;\n]*noModelsAvailable/,
  "chat composer should not disable typing because provider setup is absent",
);

assert.doesNotMatch(
  chatForm,
  /canSend=\{[^}]*noModelsAvailable/s,
  "chat composer should not block send on local provider configuration state",
);

assert.match(
  providerModels,
  /data:\s*allModels,\s*effectiveProvider:\s*null/,
  "provider model hook should expose backend models even before a local provider bucket is selected",
);
