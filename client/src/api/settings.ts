import { getApiClient } from "./client";
import type { AppSettings, AppSettingsUpdate } from "@/types/api";

export const Q_APP_SETTINGS = ["app-settings"] as const;

export async function getAppSettings(): Promise<AppSettings> {
  const { data } = await getApiClient().get<AppSettings>("/settings");
  return data;
}

export async function updateAppSettings(
  payload: AppSettingsUpdate,
): Promise<AppSettings> {
  const { data } = await getApiClient().put<AppSettings>("/settings", payload);
  return data;
}
