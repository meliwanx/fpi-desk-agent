"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { API, queryKeys } from "@/lib/constants";
import {
  COMPANY_SESSION_CHANGED_EVENT,
  readCompanySession,
} from "@/lib/company-auth";
import { enterpriseApi } from "@/lib/enterprise-api";

export interface AppAnnouncement {
  id: string;
  content: string;
  published_at: string;
}

interface AppAnnouncementResponse {
  announcement: AppAnnouncement | null;
  checked_at: string;
}

function useHasCompanySession(): boolean {
  const [hasSession, setHasSession] = useState(() => Boolean(readCompanySession()?.token));

  useEffect(() => {
    const update = () => setHasSession(Boolean(readCompanySession()?.token));
    window.addEventListener(COMPANY_SESSION_CHANGED_EVENT, update);
    return () => window.removeEventListener(COMPANY_SESSION_CHANGED_EVENT, update);
  }, []);

  return hasSession;
}

export function useAnnouncement() {
  const queryClient = useQueryClient();
  const hasCompanySession = useHasCompanySession();
  const query = useQuery({
    queryKey: queryKeys.announcement,
    queryFn: () => enterpriseApi.get<AppAnnouncementResponse>(API.APP.ANNOUNCEMENT),
    enabled: hasCompanySession,
    staleTime: 0,
    refetchInterval: 30_000,
    retry: false,
  });

  const markReadMutation = useMutation({
    mutationFn: (announcementId: string) =>
      enterpriseApi.post<{ ok: boolean }>(
        `${API.APP.ANNOUNCEMENT}/${encodeURIComponent(announcementId)}/read`,
      ),
    onSuccess: () => {
      queryClient.setQueryData<AppAnnouncementResponse>(queryKeys.announcement, (current) => ({
        checked_at: current?.checked_at ?? new Date().toISOString(),
        announcement: null,
      }));
      void queryClient.invalidateQueries({ queryKey: queryKeys.announcement });
    },
  });

  return {
    announcement: query.data?.announcement ?? null,
    isLoading: query.isLoading,
    error: query.error,
    markAnnouncementRead: markReadMutation.mutateAsync,
    isMarkingRead: markReadMutation.isPending,
    refetch: query.refetch,
  };
}
