"use client";

import { useMemo } from "react";
import { useModelPolicy } from "@/hooks/use-model-policy";
import { useModels } from "@/hooks/use-models";
import { useSettingsStore } from "@/stores/settings-store";
import { isByokProviderId, isCustomEndpointProviderId, providerBucket } from "@/lib/providers";

export function useProviderModels() {
  const { data: allModels, isLoading, isError, error } = useModels();
  const { data: modelPolicy } = useModelPolicy();
  const activeProvider = useSettingsStore((s) => s.activeProvider);

  const providerResult = useMemo(() => {
    if (!allModels) return { data: [], effectiveProvider: null };

    const modelsForBucket = (bucket: typeof activeProvider) => {
      if (!bucket) return [];
      if (bucket === "byok") {
        // "byok" mode: show models from all BYOK providers
        // (everything except subscription, Ollama, and custom/local endpoints)
        return allModels.filter((m) => isByokProviderId(m.provider_id));
      }

      if (bucket === "custom") {
        return allModels.filter((m) => isCustomEndpointProviderId(m.provider_id));
      }

      if (bucket === "chatgpt") {
        return allModels.filter((m) => m.provider_id === "openai-subscription");
      }

      if (bucket === "ollama") {
        return allModels.filter((m) => m.provider_id === "ollama");
      }

      if (bucket === "rapid-mlx") {
        return allModels.filter((m) => m.provider_id === "rapid-mlx");
      }

      return [];
    };

    const defaultBucket = modelPolicy?.default_provider_id
      ? providerBucket(modelPolicy.default_provider_id)
      : null;
    const activeModels = modelsForBucket(activeProvider);
    if (activeModels.length > 0) {
      return { data: activeModels, effectiveProvider: activeProvider };
    }

    const defaultModels = modelsForBucket(defaultBucket);
    if (defaultModels.length > 0) {
      return {
        data: defaultModels,
        effectiveProvider: defaultBucket,
      };
    }

    return { data: allModels, effectiveProvider: null };
  }, [allModels, activeProvider, modelPolicy?.default_provider_id]);

  return {
    data: providerResult.data,
    allModels,
    isLoading,
    isError,
    error,
    activeProvider: providerResult.effectiveProvider,
  };
}
