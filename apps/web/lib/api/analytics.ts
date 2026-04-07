import { apiClient } from "./client";
import type { Analytics } from "@/types/api";

export async function getAnalytics(): Promise<Analytics> {
  return apiClient.get("api/v1/analytics").json<Analytics>();
}
