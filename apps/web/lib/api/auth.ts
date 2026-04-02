import ky from "ky";
import { API_BASE_URL } from "@/lib/constants";
import type { Tenant, User, TokenResponse } from "@/types/api";

const base = ky.create({ prefixUrl: API_BASE_URL, credentials: "include" });

export async function getTenantBySlug(slug: string): Promise<Tenant> {
  // Backend returns { tenant_id, name, slug } — map tenant_id → id
  const data = await base
    .get(`auth/tenant-by-slug/${slug}`)
    .json<{ tenant_id: string; name: string; slug: string }>();
  return { id: data.tenant_id, name: data.name, slug: data.slug, created_at: "" };
}

export async function login(
  tenantId: string,
  email: string,
  password: string
): Promise<TokenResponse> {
  return base
    .post("auth/login", { json: { tenant_id: tenantId, email, password } })
    .json<TokenResponse>();
}

export async function register(
  companyName: string,
  slug: string,
  email: string,
  password: string
): Promise<TokenResponse> {
  // Backend returns only { access_token, token_type } — caller fetches user/tenant separately
  return base
    .post("auth/register", {
      json: { company_name: companyName, slug, email, password },
    })
    .json<TokenResponse>();
}

export async function getMe(token: string): Promise<User> {
  return base
    .get("auth/me", { headers: { Authorization: `Bearer ${token}` } })
    .json<User>();
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
  token: string
): Promise<void> {
  // 204 No Content — do NOT call .json(), it would throw on an empty body
  await base.post("auth/change-password", {
    json: { current_password: currentPassword, new_password: newPassword },
    headers: { Authorization: `Bearer ${token}` },
  });
}
