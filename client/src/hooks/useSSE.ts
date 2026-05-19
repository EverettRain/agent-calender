import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  fetchEventSource,
  type EventSourceMessage,
} from "@microsoft/fetch-event-source";
import { useSettings } from "@/store/settings";
import { usePreferences } from "@/store/preferences";
import { Q_REMINDERS } from "@/api/reminders";
import { formatLocalTime } from "@/lib/utils";
import type { Reminder, ReminderDuePayload, ServerEventType } from "@/types/api";

const RETRY_INTERVAL_MS = 3_000;

class RetriableError extends Error {}
class FatalError extends Error {}

/**
 * Subscribe to /stream and:
 *  - invalidate the reminders query on any reminder_* event
 *  - fire a native OS notification on reminder_due via the Electron preload bridge
 */
export function useSSE(): void {
  const serverUrl = useSettings((s) => s.serverUrl);
  const apiToken = useSettings((s) => s.apiToken);
  const qc = useQueryClient();

  const handlersRef = useRef({ qc });
  handlersRef.current.qc = qc;

  useEffect(() => {
    if (!serverUrl || !apiToken) return;
    const ctrl = new AbortController();

    void fetchEventSource(`${serverUrl}/stream`, {
      signal: ctrl.signal,
      headers: { Authorization: `Bearer ${apiToken}` },
      openWhenHidden: true, // keep streaming when Electron window is in background

      async onopen(response) {
        if (response.ok) return;
        if (response.status === 401 || response.status === 403) {
          throw new FatalError(`SSE auth failed: ${response.status}`);
        }
        throw new RetriableError();
      },

      onmessage(msg: EventSourceMessage) {
        const eventType = (msg.event || "message") as ServerEventType;
        let data: unknown = null;
        if (msg.data) {
          try {
            data = JSON.parse(msg.data);
          } catch {
            data = msg.data;
          }
        }
        handleEvent(eventType, data);
      },

      onerror(err) {
        if (err instanceof FatalError) {
          console.error("SSE 致命错误，已停止:", err.message);
          throw err; // stop retrying
        }
        console.warn("SSE 连接异常，", RETRY_INTERVAL_MS, "ms 后重连:", err);
        return RETRY_INTERVAL_MS;
      },
    });

    return () => {
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverUrl, apiToken]);
}

function handleEvent(type: ServerEventType, data: unknown): void {
  const qc = (window as unknown as { __qc?: import("@tanstack/react-query").QueryClient })
    .__qc;

  // Always invalidate on data-changing events
  if (
    type === "reminder_created" ||
    type === "reminder_updated" ||
    type === "reminder_deleted"
  ) {
    qc?.invalidateQueries({ queryKey: Q_REMINDERS });
  }

  if (type === "reminder_due" && isReminderDue(data)) {
    const prefs = usePreferences.getState();
    if (prefs.notificationsEnabled) {
      fireNativeNotification(data, prefs.notificationsSilent);
    }
    qc?.invalidateQueries({ queryKey: Q_REMINDERS });
  }
}

function isReminderDue(x: unknown): x is ReminderDuePayload {
  return (
    !!x && typeof x === "object" && "reminder_id" in x && "offset_minutes" in x
  );
}

function fireNativeNotification(p: ReminderDuePayload, silent: boolean): void {
  const electron = window.electron;
  const title = buildNotifTitle(p);
  const body = buildNotifBody(p);
  if (!electron) {
    if ("Notification" in window) {
      try {
        new Notification(title, { body, silent });
      } catch {
        /* permission denied or unsupported */
      }
    }
    return;
  }
  void electron.notify({ title, body, silent });
}

function buildNotifTitle(p: ReminderDuePayload): string {
  if (p.kind === "deadline") {
    if (p.offset_minutes >= 1440) {
      const days = Math.round(p.offset_minutes / 1440);
      return `📌 截止前 ${days} 天提醒`;
    }
    if (p.offset_minutes >= 60) {
      const hours = Math.round(p.offset_minutes / 60);
      return `📌 截止前 ${hours} 小时提醒`;
    }
    if (p.offset_minutes > 0) return `📌 截止前 ${p.offset_minutes} 分钟`;
    return "📌 截止时间到";
  }
  // event
  if (p.offset_minutes > 0) return `📅 事件还有 ${p.offset_minutes} 分钟`;
  return "📅 事件开始时间";
}

function buildNotifBody(p: ReminderDuePayload): string {
  return `${p.title} · ${formatLocalTime(p.target_at)}`;
}

/**
 * Expose the QueryClient to the event handler via window. Call once in App.
 * Avoids stale closures while keeping handleEvent a plain function.
 */
export function bindQueryClient(qc: import("@tanstack/react-query").QueryClient): void {
  (window as unknown as { __qc?: import("@tanstack/react-query").QueryClient }).__qc =
    qc;
}

export type { Reminder };
