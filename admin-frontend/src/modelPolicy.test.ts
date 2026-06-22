import assert from "node:assert/strict";
import test from "node:test";
import { removeModelFromPolicy, setDefaultModelInPolicy, updateModelInPolicy } from "./modelPolicy.ts";

const basePolicy = {
  default_provider_id: "custom_onlyme",
  default_model_id: "gpt-5.5",
  models: [
    {
      provider_id: "custom_onlyme",
      id: "gpt-5.5",
      name: "GPT-5.5",
      protocol: "openai_compatible",
      base_url: "https://sub2api.onlymeok.com/v1",
      api_key: "",
    },
    {
      provider_id: "custom_npimvg",
      id: "gpt-5.5",
      name: "GPT-5.5-1",
      protocol: "openai_compatible",
      base_url: "https://claude.hangzhoupuyu.work/",
      api_key: "",
    },
  ],
};

test("removing the current default model moves the default to a remaining allowed model", () => {
  const next = removeModelFromPolicy(basePolicy, 0);

  assert.equal(next.models.length, 1);
  assert.equal(next.default_provider_id, "custom_npimvg");
  assert.equal(next.default_model_id, "gpt-5.5");
});

test("removing a non-default model keeps the current default", () => {
  const next = removeModelFromPolicy(basePolicy, 1);

  assert.equal(next.models.length, 1);
  assert.equal(next.default_provider_id, "custom_onlyme");
  assert.equal(next.default_model_id, "gpt-5.5");
});

test("editing the current default model id keeps the default in sync", () => {
  const next = updateModelInPolicy(basePolicy, 0, {
    provider_id: "custom_renamed",
    id: "claude-sonnet-4",
  });

  assert.equal(next.default_provider_id, "custom_renamed");
  assert.equal(next.default_model_id, "claude-sonnet-4");
});

test("selecting a model as default writes its provider and model ids", () => {
  const next = setDefaultModelInPolicy(basePolicy, 1);

  assert.equal(next.default_provider_id, "custom_npimvg");
  assert.equal(next.default_model_id, "gpt-5.5");
});
