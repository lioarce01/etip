import { apiClient } from "./client";
import type { Tenant } from "@/types/api";

export async function getMyTenant(): Promise<Tenant> {
  return apiClient.get("tenants/me").json<Tenant>();
}

export async function updateTenant(payload: { name?: string }): Promise<Tenant> {
  return apiClient
    .patch("tenants/me", { json: payload })
    .json<Tenant>();
}
