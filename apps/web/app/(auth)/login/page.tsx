"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, Check } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login, selectTenant, getMe, getMyTenants } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/auth";
import type { Tenant, LoginResponse } from "@/types/api";

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const setAuth = useAuthStore((s) => s.setAuth);
  const setAvailableTenants = useAuthStore((s) => s.setAvailableTenants);

  const [step, setStep] = useState<"credentials" | "tenant-select">("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    try {
      const response = await login(email, password);

      // Single tenant — direct login
      if (response?.access_token) {
        const user = await getMe(response.access_token);
        const myTenants = await getMyTenants(response.access_token);
        setAvailableTenants(myTenants);
        // Find the tenant for this token
        const tenant = myTenants.find((t) => t.id === user.tenant_id);
        if (tenant) {
          setAuth(response.access_token, user, tenant);
          queryClient.invalidateQueries();
          router.push("/overview");
        }
        return;
      }

      // Multiple tenants — show selection
      if (Array.isArray(response?.tenants) && response.tenants.length > 0) {
        setTenants(response.tenants);
        setStep("tenant-select");
        return;
      }

      toast.error("No tenants found for this email.");
    } catch (err: unknown) {
      if (err instanceof TypeError) {
        toast.error("Cannot reach the server. Make sure the API is running.");
      } else {
        toast.error("Invalid email or password.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleTenantSelect(tenant: Tenant) {
    setLoading(true);
    try {
      const response = await selectTenant(tenant.id);
      const user = await getMe(response.access_token);
      const myTenants = await getMyTenants(response.access_token);
      setAvailableTenants(myTenants);
      setAuth(response.access_token, user, tenant);
      queryClient.invalidateQueries();
      router.push("/overview");
    } catch {
      toast.error("Failed to select workspace. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      {step === "credentials" ? (
        <>
          <h2 className="mb-1 text-xl font-semibold tracking-tight text-foreground">
            Sign in
          </h2>
          <p className="mb-6 text-sm text-[var(--gray-500)]">
            Enter your email and password to continue.
          </p>

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoFocus
                autoComplete="email"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading || !email || !password}>
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                "Sign in"
              )}
            </Button>
          </form>
        </>
      ) : (
        <>
          <h2 className="mb-1 text-xl font-semibold tracking-tight text-foreground">
            Select a workspace
          </h2>
          <p className="mb-6 text-sm text-[var(--gray-500)]">
            You have access to multiple workspaces. Choose one to continue.
          </p>

          <div className="space-y-2">
            {tenants.map((tenant) => (
              <button
                key={tenant.id}
                onClick={() => handleTenantSelect(tenant)}
                disabled={loading}
                className="w-full rounded-md border border-[var(--gray-200)] bg-white p-3 text-left transition-colors hover:bg-[var(--gray-50)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="font-medium text-foreground">{tenant.name}</div>
                <div className="text-sm text-[var(--gray-500)]">{tenant.slug}</div>
              </button>
            ))}
          </div>

          <button
            type="button"
            className="mt-4 text-xs text-[var(--gray-500)] hover:text-foreground transition-colors duration-150"
            onClick={() => {
              setStep("credentials");
              setTenants([]);
            }}
            disabled={loading}
          >
            ← Back to email
          </button>
        </>
      )}

      <p className="mt-6 text-center text-sm text-[var(--gray-500)]">
        No account?{" "}
        <Link
          href="/register"
          className="text-[var(--blue-600)] hover:underline underline-offset-4"
        >
          Register
        </Link>
      </p>
    </div>
  );
}
