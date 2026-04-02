"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { register, getMe, getTenantBySlug } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/auth";

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [companyName, setCompanyName] = useState("");
  const [slug, setSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [slugEdited, setSlugEdited] = useState(false);

  function handleCompanyNameChange(v: string) {
    setCompanyName(v);
    if (!slugEdited) setSlug(slugify(v));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const { access_token } = await register(companyName, slug, email, password);
      const [user, tenant] = await Promise.all([
        getMe(access_token),
        getTenantBySlug(slug),
      ]);
      setAuth(access_token, user, tenant);
      router.push("/overview");
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Registration failed. Try again.";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  const slugValid = /^[a-z0-9-]+$/.test(slug) && slug.length >= 2;

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold tracking-tight text-foreground">
        Create your workspace
      </h2>
      <p className="mb-6 text-sm text-[var(--gray-500)]">
        Set up your company&apos;s talent intelligence platform.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="company-name">Company name</Label>
          <Input
            id="company-name"
            placeholder="Acme Corp"
            value={companyName}
            onChange={(e) => handleCompanyNameChange(e.target.value)}
            autoFocus
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="slug">
            Workspace slug{" "}
            <span className="text-[var(--gray-400)] font-normal">(used to log in)</span>
          </Label>
          <Input
            id="slug"
            placeholder="acme"
            value={slug}
            onChange={(e) => {
              setSlug(e.target.value);
              setSlugEdited(true);
            }}
          />
          {slug && !slugValid && (
            <p className="text-xs text-[var(--red-500)]">
              Only lowercase letters, numbers, and hyphens. Min 2 chars.
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="email">Admin email</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@acme.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
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
            autoComplete="new-password"
          />
        </div>

        <Button
          type="submit"
          className="w-full"
          disabled={loading || !slugValid}
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating workspace...
            </>
          ) : (
            "Create workspace"
          )}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-[var(--gray-500)]">
        Already have an account?{" "}
        <Link
          href="/login"
          className="text-[var(--blue-600)] hover:underline underline-offset-4"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}
