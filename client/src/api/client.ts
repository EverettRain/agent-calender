import axios, { AxiosError, type AxiosInstance } from "axios";
import { useSettings } from "@/store/settings";

let cached: { client: AxiosInstance; key: string } | null = null;

/**
 * Build an axios instance bound to the current Settings. Re-created when
 * serverUrl or apiToken change so each request carries fresh auth.
 */
export function getApiClient(): AxiosInstance {
  const { serverUrl, apiToken } = useSettings.getState();
  const key = `${serverUrl}::${apiToken}`;

  if (cached && cached.key === key) {
    return cached.client;
  }

  const client = axios.create({
    baseURL: serverUrl,
    // LLM extraction (generate + verify) typically takes 15-25s; DeepSeek can
    // spike to 40s+. 90s leaves headroom without leaving the user staring at
    // a "timeout" toast when the data actually went through.
    timeout: 90_000,
    headers: apiToken ? { Authorization: `Bearer ${apiToken}` } : undefined,
  });

  client.interceptors.response.use(
    (r) => r,
    (err: AxiosError) => {
      if (err.response?.status === 401) {
        // Token mismatch — likely outdated client config
        console.warn("API 返回 401，请检查 Settings 里的 Token");
      }
      return Promise.reject(err);
    },
  );

  cached = { client, key };
  return client;
}

/**
 * Subscribe Settings store so the cached client invalidates automatically.
 * Call once during app bootstrap.
 */
export function wireSettingsToClient(): void {
  useSettings.subscribe(() => {
    cached = null;
  });
}
