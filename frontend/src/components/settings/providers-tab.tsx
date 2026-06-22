"use client";

import { useEffect } from "react";
import { CheckCircle2, LockKeyhole } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { API, queryKeys } from "@/lib/constants";
import { useModelPolicy } from "@/hooks/use-model-policy";
import { useModels } from "@/hooks/use-models";
import { useSettingsStore } from "@/stores/settings-store";
import { providerBucket } from "@/lib/providers";
import type { ProviderInfo } from "@/types/usage";

export function ProvidersTab() {
  const setActiveProvider = useSettingsStore((s) => s.setActiveProvider);
  const setSelectedModel = useSettingsStore((s) => s.setSelectedModel);

  const { data: allModels } = useModels();
  const { data: modelPolicy } = useModelPolicy();
  const { data: providers } = useQuery({
    queryKey: queryKeys.providers,
    queryFn: () => api.get<ProviderInfo[]>(API.CONFIG.PROVIDERS),
  });

  const defaultProviderId = modelPolicy?.default_provider_id ?? "";
  const defaultModelId = modelPolicy?.default_model_id ?? "";
  const managedProvider = providers?.find((p) => p.id === defaultProviderId);
  const managedModel =
    allModels?.find(
      (m) => m.provider_id === defaultProviderId && m.id === defaultModelId,
    ) ??
    allModels?.find(
      (m) =>
        m.provider_id === defaultProviderId &&
        defaultModelId &&
        m.id.endsWith(`/${defaultModelId}`),
    );

  useEffect(() => {
    if (!defaultProviderId) return;
    setActiveProvider(providerBucket(defaultProviderId));
    if (managedModel) {
      setSelectedModel(managedModel.id, managedModel.provider_id);
    }
  }, [defaultProviderId, managedModel, setActiveProvider, setSelectedModel]);

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-[var(--border-default)] bg-[var(--surface-secondary)] p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <LockKeyhole className="h-4 w-4 text-[var(--brand-primary)]" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                企业托管模型
              </h3>
            </div>
          </div>
          <span className="inline-flex shrink-0 items-center gap-1 rounded-md border border-[var(--color-success)]/30 bg-[var(--color-success)]/10 px-2 py-1 text-xs font-medium text-[var(--color-success)]">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {managedProvider?.status === "connected" ? "已连接" : "托管"}
          </span>
        </div>
      </section>
    </div>
  );
}
