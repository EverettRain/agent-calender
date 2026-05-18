import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Q_REMINDERS,
  deleteReminder,
  ingestText,
  listReminders,
  markDone,
  updateReminder,
  type ListParams,
} from "@/api/reminders";
import { useSettings } from "@/store/settings";
import type { ReminderUpdate } from "@/types/api";

export function useReminders(params: ListParams = {}) {
  const isConfigured = useSettings((s) => s.isConfigured());
  return useQuery({
    queryKey: [...Q_REMINDERS, params],
    queryFn: () => listReminders(params),
    enabled: isConfigured,
    refetchOnWindowFocus: true,
    staleTime: 10_000,
  });
}

export function useIngest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ingestText,
    onSuccess: () => qc.invalidateQueries({ queryKey: Q_REMINDERS }),
  });
}

export function useUpdateReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ReminderUpdate }) =>
      updateReminder(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: Q_REMINDERS }),
  });
}

export function useMarkDone() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => markDone(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: Q_REMINDERS }),
  });
}

export function useDeleteReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteReminder(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: Q_REMINDERS }),
  });
}
