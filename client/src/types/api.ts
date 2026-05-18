/**
 * TypeScript types mirroring server/app/schemas.py.
 * Keep in sync when API surface changes.
 */

export type ReminderKind = "event" | "deadline";

export type ReminderStatus =
  | "pending"
  | "pending_review"
  | "notified"
  | "done"
  | "cancelled";

export interface Reminder {
  id: string;
  kind: ReminderKind;
  title: string;
  description: string | null;
  target_at: string; // ISO 8601, UTC
  end_at: string | null;
  duration_minutes: number | null;
  location: string | null;
  participants: string[];
  advance_reminders_minutes: number[];
  fired_offsets: number[];
  status: ReminderStatus;
  source_text: string;
  source_channel: string;
  llm_model: string | null;
  extraction_group_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface IngestRequest {
  text: string;
  source_channel?: string;
}

export interface IngestResponse {
  extraction_group_id: string;
  status: "success" | "pending_review";
  reminders: Reminder[];
  attempts: number;
  total_tokens: number;
}

export interface ReminderUpdate {
  title?: string;
  description?: string | null;
  target_at?: string;
  end_at?: string | null;
  duration_minutes?: number | null;
  location?: string | null;
  participants?: string[];
  advance_reminders_minutes?: number[];
  status?: ReminderStatus;
}

export interface ManualReminderCreate {
  kind: ReminderKind;
  title: string;
  description?: string | null;
  target_at: string;
  end_at?: string | null;
  duration_minutes?: number | null;
  location?: string | null;
  participants?: string[];
  advance_reminders_minutes?: number[];
}

// ===== SSE event payloads =====

export type ServerEventType =
  | "reminder_created"
  | "reminder_updated"
  | "reminder_deleted"
  | "reminder_due"
  | "ping";

export interface ReminderDuePayload {
  reminder_id: string;
  kind: ReminderKind;
  title: string;
  target_at: string;
  offset_minutes: number;
  minutes_to_target: number;
}

export interface ReminderDeletedPayload {
  reminder_id: string;
}
