import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Q_APP_SETTINGS,
  getAppSettings,
  updateAppSettings,
} from "@/api/settings";
import { useSettings } from "@/store/settings";
import type { AppSettingsUpdate } from "@/types/api";

export function useAppSettings() {
  const isConfigured = useSettings((s) => s.isConfigured());
  return useQuery({
    queryKey: Q_APP_SETTINGS,
    queryFn: getAppSettings,
    enabled: isConfigured,
    staleTime: 30_000,
  });
}

export function useUpdateAppSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: AppSettingsUpdate) => updateAppSettings(payload),
    onSuccess: (data) => qc.setQueryData(Q_APP_SETTINGS, data),
  });
}
