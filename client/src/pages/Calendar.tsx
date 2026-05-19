import { useMemo, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import type { EventInput, EventClickArg } from "@fullcalendar/core";
import { X } from "lucide-react";
import ReminderCard from "@/components/ReminderCard";
import Loader from "@/components/Loader";
import { useReminders } from "@/hooks/useReminders";
import { usePreferences } from "@/store/preferences";
import type { Reminder } from "@/types/api";

const COLOR_EVENT = "#6366f1"; // indigo-500
const COLOR_EVENT_LIGHT = "#a5b4fc"; // indigo-300
const COLOR_DEADLINE = "#f59e0b"; // amber-500
const COLOR_DEADLINE_LIGHT = "#fcd34d"; // amber-300
const COLOR_REVIEW = "#ef4444"; // red-500
const COLOR_DONE = "#94a3b8"; // slate-400

export default function Calendar() {
  // Pull a wider range than Today so the calendar can navigate freely.
  const range = useMemo(() => {
    const now = new Date();
    const start = new Date(now);
    start.setMonth(start.getMonth() - 1);
    const end = new Date(now);
    end.setMonth(end.getMonth() + 3);
    return { from: start.toISOString(), to: end.toISOString() };
  }, []);

  const { data, isError, error } = useReminders({
    ...range,
    limit: 1000,
  });

  const showDone = usePreferences((s) => s.showDone);

  const [selected, setSelected] = useState<Reminder | null>(null);

  const events = useMemo<EventInput[]>(() => {
    if (!data) return [];
    return data
      .filter((r) => {
        // Hard: never show deleted (cancelled) items on the calendar
        if (r.status === "cancelled") return false;
        // Soft: respect the "show done" preference for finished items
        if (r.status === "done" && !showDone) return false;
        return true;
      })
      .map((r) => reminderToEvent(r));
  }, [data, showDone]);

  const onEventClick = (arg: EventClickArg) => {
    const id = arg.event.extendedProps.reminderId as string;
    const found = data?.find((r) => r.id === id);
    setSelected(found ?? null);
  };

  // First-render guard: don't paint an empty FullCalendar — show a full block
  // loader instead. Once `data` exists, subsequent SSE-triggered refetches
  // update events in place without flashing.
  const ready = data !== undefined;

  return (
    <div className="relative h-full p-4 flex flex-col min-w-[640px] min-h-[480px]">
      {isError && (
        <div className="text-sm text-red-500 mb-2">
          加载失败：{(error as Error)?.message ?? "未知错误"}
        </div>
      )}

      {!ready ? (
        <div className="card flex flex-1 items-center justify-center min-h-[400px]">
          <Loader variant="block" size="lg" label="加载日历数据…" />
        </div>
      ) : (
        <div className="fc-shell card p-3 flex flex-1 flex-col min-h-[400px]">
          <FullCalendar
            plugins={[dayGridPlugin, timeGridPlugin]}
            initialView="dayGridMonth"
            headerToolbar={{
              left: "prev,next today",
              center: "title",
              right: "dayGridMonth,timeGridWeek",
            }}
            buttonText={{
              today: "今天",
              month: "月",
              week: "周",
            }}
            firstDay={1}
            locale="zh-cn"
            height="100%"
            expandRows
            dayMaxEvents={4}
            eventDisplay="block"
            eventClick={onEventClick}
            events={events}
            eventTimeFormat={{
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            }}
            slotLabelFormat={{
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            }}
          />
        </div>
      )}

      {selected && (
        <DetailOverlay reminder={selected} onClose={() => setSelected(null)} />
      )}

      <style>{customCalendarStyles}</style>
    </div>
  );
}

function reminderToEvent(r: Reminder): EventInput {
  const isReview = r.status === "pending_review";
  const isDone = r.status === "done" || r.status === "cancelled";
  const isDeadline = r.kind === "deadline";

  let backgroundColor: string;
  let borderColor: string;

  if (isReview) {
    backgroundColor = COLOR_REVIEW;
    borderColor = COLOR_REVIEW;
  } else if (isDone) {
    backgroundColor = COLOR_DONE;
    borderColor = COLOR_DONE;
  } else if (isDeadline) {
    backgroundColor = COLOR_DEADLINE;
    borderColor = COLOR_DEADLINE_LIGHT;
  } else {
    backgroundColor = COLOR_EVENT;
    borderColor = COLOR_EVENT_LIGHT;
  }

  // For deadlines, show as point events at target_at; FullCalendar handles all-day
  // logic via the `allDay` flag (we keep it timed for precision).
  const start = r.target_at;
  let end: string | undefined;
  if (r.kind === "event") {
    if (r.end_at) end = r.end_at;
    else if (r.duration_minutes) {
      end = new Date(
        new Date(r.target_at).getTime() + r.duration_minutes * 60_000,
      ).toISOString();
    }
  }

  return {
    id: r.id,
    title: `${isDeadline ? "📌 " : ""}${r.title}`,
    start,
    end,
    backgroundColor,
    borderColor,
    textColor: "#ffffff",
    classNames: isDone ? ["opacity-60", "line-through"] : [],
    extendedProps: { reminderId: r.id, kind: r.kind, status: r.status },
  };
}

function DetailOverlay({
  reminder,
  onClose,
}: {
  reminder: Reminder;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 dark:bg-slate-950/60 p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="absolute -top-3 -right-3 z-10 rounded-full bg-white dark:bg-slate-800 shadow p-1"
          onClick={onClose}
          aria-label="关闭"
        >
          <X className="h-4 w-4" />
        </button>
        <ReminderCard reminder={reminder} />
      </div>
    </div>
  );
}

// Light/dark tweaks for FullCalendar; the lib ships its own CSS but we override
// a few rules to fit our slate palette. Kept inline so the page is self-contained.
const customCalendarStyles = `
  /* Allow FullCalendar to grow with its flex parent */
  .fc-shell { min-height: 0; }
  .fc-shell .fc { height: 100% !important; }
  .fc-shell .fc-view-harness { flex: 1 1 auto; }

  .fc-shell .fc {
    --fc-border-color: rgb(226 232 240);
    --fc-page-bg-color: transparent;
    --fc-neutral-bg-color: rgb(248 250 252);
    --fc-today-bg-color: rgb(238 242 255);
    font-size: 0.875rem;
  }
  .dark .fc-shell .fc {
    --fc-border-color: rgb(51 65 85);
    --fc-neutral-bg-color: rgb(30 41 59);
    --fc-today-bg-color: rgb(30 27 75);
    color: rgb(226 232 240);
  }
  .fc-shell .fc .fc-button-primary {
    background: rgb(99 102 241);
    border-color: rgb(99 102 241);
  }
  .fc-shell .fc .fc-button-primary:hover {
    background: rgb(79 70 229);
    border-color: rgb(79 70 229);
  }
  .fc-shell .fc .fc-button-primary:not(:disabled).fc-button-active,
  .fc-shell .fc .fc-button-primary:not(:disabled):active {
    background: rgb(67 56 202);
    border-color: rgb(67 56 202);
  }
  .fc-shell .fc-event {
    cursor: pointer;
    border-radius: 4px;
    padding: 0 4px;
    font-size: 0.75rem;
  }
  .fc-shell .fc-toolbar-title {
    font-size: 1.125rem;
    font-weight: 600;
  }
`;
