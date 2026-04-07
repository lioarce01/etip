import ky from "ky";
import { API_BASE_URL } from "@/lib/constants";
import type { Tenant, User, TokenResponse, LoginResponse } from "@/types/api";

const base = ky.create({ prefixUrl: API_BASE_URL, credentials: "include" });

export async function getTenantBySlug(slug: string): Promise<Tenant> {
  return base
    .get(`auth/tenant-by-slug/${slug}`)
    .json<Tenant>();
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  return base
    .post("auth/login", { json: { email, password } })
    .json<LoginResponse>();
}

export async function selectTenant(tenantId: string): Promise<TokenResponse> {
  return base
    .post("auth/select-tenant", { json: { tenant_id: tenantId } })
    .json<TokenResponse>();
}

export async function getMyTenants(token: string): Promise<Tenant[]> {
  return base
    .get("auth/tenants", { headers: { Authorization: `Bearer ${token}` } })
    .json<Tenant[]>();
}

export async function switchTenant(tenantId: string, token: string): Promise<TokenResponse> {
  return base
    .post("auth/switch-tenant", {
      json: { tenant_id: tenantId },
      headers: { Authorization: `Bearer ${token}` },
    })
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
