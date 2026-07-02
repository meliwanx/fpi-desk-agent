export interface ModelEntry {
  provider_id: string;
  id: string;
  name: string;
  protocol: string;
  base_url: string;
  enabled?: boolean;
  api_key?: string;
  masked_key?: string;
  test_token?: string;
}

export interface ModelPolicy {
  default_provider_id: string;
  default_model_id: string;
  models: ModelEntry[];
}

export const DEFAULT_MODEL_PROTOCOL = "openai_compatible";

function modelMatchesDefault(model: ModelEntry, policy: ModelPolicy): boolean {
  return model.provider_id === policy.default_provider_id && model.id === policy.default_model_id;
}

function modelEnabled(model: ModelEntry): boolean {
  return model.enabled !== false;
}

function firstCompleteModel(models: ModelEntry[]): ModelEntry | null {
  return models.find((model) => modelEnabled(model) && model.provider_id.trim() && model.id.trim()) || null;
}

export function ensureModelPolicyDefault(policy: ModelPolicy): ModelPolicy {
  const currentDefaultExists = policy.models.some((model) => modelEnabled(model) && modelMatchesDefault(model, policy));
  if (currentDefaultExists) return policy;

  const nextDefault = firstCompleteModel(policy.models) || policy.models[0];
  return {
    ...policy,
    default_provider_id: nextDefault?.provider_id || "",
    default_model_id: nextDefault?.id || "",
  };
}

export function normaliseModelPolicy(policy: ModelPolicy): ModelPolicy {
  return ensureModelPolicyDefault({
    ...policy,
    models: policy.models.map((model) => ({
      ...model,
      protocol: model.protocol || DEFAULT_MODEL_PROTOCOL,
      base_url: model.base_url || "",
      enabled: model.enabled !== false,
      api_key: "",
    })),
  });
}

export function updateModelInPolicy(policy: ModelPolicy, index: number, patch: Partial<ModelEntry>): ModelPolicy {
  const original = policy.models[index];
  const models = policy.models.map((model, i) => (i === index ? { ...model, ...patch } : model));
  const next = { ...policy, models };
  if (original && modelMatchesDefault(original, policy)) {
    const updated = models[index];
    return ensureModelPolicyDefault({
      ...next,
      default_provider_id: updated?.provider_id || "",
      default_model_id: updated?.id || "",
    });
  }
  return ensureModelPolicyDefault(next);
}

export function addModelToPolicy(policy: ModelPolicy, model: ModelEntry): ModelPolicy {
  return ensureModelPolicyDefault({
    ...policy,
    models: [...policy.models, { ...model, enabled: model.enabled !== false }],
  });
}

export function setDefaultModelInPolicy(policy: ModelPolicy, index: number): ModelPolicy {
  const model = policy.models[index];
  if (!model || model.enabled === false || !model.provider_id.trim() || !model.id.trim()) {
    return ensureModelPolicyDefault(policy);
  }
  return {
    ...policy,
    default_provider_id: model.provider_id,
    default_model_id: model.id,
  };
}
