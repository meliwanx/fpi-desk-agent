"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { API } from "@/lib/constants";
import type { ModelInfo } from "@/types/model";

export interface CompanyModelPolicy {
  default_provider_id: string;
  default_model_id: string;
  models: ModelInfo[];
}

export function useModelPolicy() {
  return useQuery({
    queryKey: ["model-policy"],
    queryFn: () => api.get<CompanyModelPolicy>(API.MODEL_POLICY),
    retry: false,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
    refetchOnWindowFocus: true,
  });
}
