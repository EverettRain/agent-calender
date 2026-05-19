import { getApiClient } from "./client";
import type { Tag, TagCreate, TagUpdate } from "@/types/api";

export const Q_TAGS = ["tags"] as const;

export async function listTags(): Promise<Tag[]> {
  const { data } = await getApiClient().get<Tag[]>("/tags");
  return data;
}

export async function createTag(payload: TagCreate): Promise<Tag> {
  const { data } = await getApiClient().post<Tag>("/tags", payload);
  return data;
}

export async function updateTag(id: string, payload: TagUpdate): Promise<Tag> {
  const { data } = await getApiClient().put<Tag>(`/tags/${id}`, payload);
  return data;
}

export async function deleteTag(id: string): Promise<void> {
  await getApiClient().delete(`/tags/${id}`);
}
