import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Q_TAGS,
  createTag,
  deleteTag,
  listTags,
  updateTag,
} from "@/api/tags";
import {
  Q_GROUPS,
  createGroup,
  deleteGroup,
  listGroups,
  updateGroup,
} from "@/api/groups";
import { Q_REMINDERS } from "@/api/reminders";
import { useSettings } from "@/store/settings";
import type { TagCreate, TagUpdate, GroupCreate, GroupUpdate } from "@/types/api";

export function useTags() {
  const isConfigured = useSettings((s) => s.isConfigured());
  return useQuery({
    queryKey: Q_TAGS,
    queryFn: listTags,
    enabled: isConfigured,
    staleTime: 30_000,
  });
}

export function useCreateTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: TagCreate) => createTag(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: Q_TAGS }),
  });
}

export function useUpdateTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TagUpdate }) =>
      updateTag(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: Q_TAGS });
      qc.invalidateQueries({ queryKey: Q_REMINDERS });
    },
  });
}

export function useDeleteTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTag(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: Q_TAGS });
      qc.invalidateQueries({ queryKey: Q_REMINDERS });
    },
  });
}

export function useGroups() {
  const isConfigured = useSettings((s) => s.isConfigured());
  return useQuery({
    queryKey: Q_GROUPS,
    queryFn: listGroups,
    enabled: isConfigured,
    staleTime: 30_000,
  });
}

export function useCreateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: GroupCreate) => createGroup(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: Q_GROUPS }),
  });
}

export function useUpdateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: GroupUpdate }) =>
      updateGroup(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: Q_GROUPS });
      qc.invalidateQueries({ queryKey: Q_REMINDERS });
    },
  });
}

export function useDeleteGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteGroup(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: Q_GROUPS });
      qc.invalidateQueries({ queryKey: Q_REMINDERS });
    },
  });
}
