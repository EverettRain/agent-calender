import { getApiClient } from "./client";
import type { Group, GroupCreate, GroupUpdate } from "@/types/api";

export const Q_GROUPS = ["groups"] as const;

export async function listGroups(): Promise<Group[]> {
  const { data } = await getApiClient().get<Group[]>("/groups");
  return data;
}

export async function createGroup(payload: GroupCreate): Promise<Group> {
  const { data } = await getApiClient().post<Group>("/groups", payload);
  return data;
}

export async function updateGroup(
  id: string,
  payload: GroupUpdate,
): Promise<Group> {
  const { data } = await getApiClient().put<Group>(`/groups/${id}`, payload);
  return data;
}

export async function deleteGroup(id: string): Promise<void> {
  await getApiClient().delete(`/groups/${id}`);
}
