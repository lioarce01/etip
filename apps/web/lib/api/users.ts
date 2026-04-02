import { apiClient } from "./client";
import type { User } from "@/types/api";
import type { Role } from "@/lib/constants";

export async function listUsers(): Promise<User[]> {
  const res = await apiClient.get("api/v1/users").json<{ items: User[] }>();
  return res.items;
}

export async function createUser(payload: {
  email: string;
  password: string;
  role: Role;
}): Promise<User> {
  return apiClient.post("api/v1/users", { json: payload }).json<User>();
}

export async function updateUser(
  id: string,
  payload: { role?: Role; is_active?: boolean }
): Promise<User> {
  return apiClient
    .patch(`api/v1/users/${id}`, { json: payload })
    .json<User>();
}

export async function deleteUser(id: string): Promise<void> {
  await apiClient.delete(`api/v1/users/${id}`);
}
