"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getTenantBySlug, login, getMe } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/auth";
import type { Tenant } from "@/types/api";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [step, setStep] = useState<"slug" | "credentials">("slug");
  const [slug, setSlug] = useState("");
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSlug(e: React.FormEvent) {
    e.preventDefault();
    if (!slug.trim()) return;
    setLoading(true);
    try {
      const t = await getTenantBySlug(slug.trim());
      setTenant(t);
      setStep("credentials");
    } catch {
      toast.error("Workspace not found. Check the slug and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!tenant) return;
    setLoading(true);
    try {
      const { access_token } = await login(tenant.id, email, password);
      try {
        const user = await getMe(access_token);
        setAuth(access_token, user, tenant);
        router.push("/overview");
      } catch (sessionErr) {
        console.error("[login] getMe failed after successful login:", sessionErr);
        toast.error("Login succeeded but session could not be created. Try again.");
      }
    } catch (err: unknown) {
      console.error("[login] login request failed:", err);
      if (err instanceof TypeError) {
        toast.error("Cannot reach the server. Make sure the API is running.");
      } else {
        toast.error("Invalid email or password.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold tracking-tight text-foreground">
        Sign in to your workspace
      </h2>
      <p className="mb-6 text-sm text-[var(--gray-500)]">
        Enter your company slug to continue.
      </p>

      {step === "slug" ? (
        <form onSubmit={handleSlug} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="slug">Company slug</Label>
            <Input
              id="slug"
              placeholder="acme"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              autoFocus
              autoComplete="organization"
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading || !slug.trim()}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Looking up...
              </>
            ) : (
              "Continue"
            )}
          </Button>
        </form>
      ) : (
        <form onSubmit={handleLogin} className="space-y-4">
          {/* Resolved workspace badge */}
          <div className="flex items-center justify-between rounded-md border border-[var(--gray-200)] bg-[var(--gray-100)] px-3 py-2">
            <span className="text-sm text-[var(--gray-500)]">Workspace</span>
            <span className="text-sm font-medium text-foreground">
              {tenant?.name}
            </span>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@acme.com"
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
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Signing in...
              </>
            ) : (
              "Sign in"
            )}
          </Button>

          <button
            type="button"
            className="text-xs text-[var(--gray-500)] hover:text-foreground transition-colors duration-150"
            onClick={() => {
              setStep("slug");
              setTenant(null);
            }}
          >
            ← Change workspace
          </button>
        </form>
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
