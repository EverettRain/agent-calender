import { getApiClient } from "./client";
import type {
  IngestRequest,
  IngestResponse,
  ManualReminderCreate,
  Reminder,
  ReminderKind,
  ReminderUpdate,
} from "@/types/api";

export const Q_REMINDERS = ["reminders"] as const;

export interface ListParams {
  from?: string;
  to?: string;
  status?: string;
  kind?: ReminderKind;
  limit?: number;
}

export async function listReminders(params: ListParams = {}): Promise<Reminder[]> {
  const client = getApiClient();
  const { data } = await client.get<Reminder[]>("/reminders", { params });
  return data;
}

export async function getReminder(id: string): Promise<Reminder> {
  const client = getApiClient();
  const { data } = await client.get<Reminder>(`/reminders/${id}`);
  return data;
}

export async function ingestText(payload: IngestRequest): Promise<IngestResponse> {
  const client = getApiClient();
  const { data } = await client.post<IngestResponse>("/ingest", payload);
  return data;
}

export async function createReminderManually(
  payload: ManualReminderCreate,
): Promise<Reminder> {
  const client = getApiClient();
  const { data } = await client.post<Reminder>("/reminders", payload);
  return data;
}

export async function updateReminder(
  id: string,
  payload: ReminderUpdate,
): Promise<Reminder> {
  const client = getApiClient();
  const { data } = await client.put<Reminder>(`/reminders/${id}`, payload);
  return data;
}

export async function markDone(id: string): Promise<Reminder> {
  const client = getApiClient();
  const { data } = await client.post<Reminder>(`/reminders/${id}/done`);
  return data;
}

export async function deleteReminder(id: string): Promise<void> {
  const client = getApiClient();
  await client.delete(`/reminders/${id}`);
}

export async function healthz(): Promise<{ status: string }> {
  const client = getApiClient();
  const { data } = await client.get<{ status: string }>("/healthz");
  return data;
}
