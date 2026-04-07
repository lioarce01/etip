"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { useAuthStore } from "@/lib/store/auth";
import { getMe, getMyTenants } from "@/lib/api/auth";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const setAuth = useAuthStore((s) => s.setAuth);
  const setAvailableTenants = useAuthStore((s) => s.setAvailableTenants);
  const [rehydrating, setRehydrating] = useState(true);

  useEffect(() => {
    async function rehydrateSession() {
      if (!token) {
        try {
          // Try to refresh and restore session from cookie
          const refreshResp = await fetch("/auth/refresh", {
            method: "POST",
            credentials: "include",
          });
          if (refreshResp.ok) {
            const { access_token } = await refreshResp.json();
            const user = await getMe(access_token);
            const tenants = await getMyTenants(access_token);
            const currentTenant = tenants.find((t) => t.id === user.tenant_id);
            if (currentTenant) {
              setAuth(access_token, user, currentTenant);
              setAvailableTenants(tenants);
              setRehydrating(false);
              return;
            }
          }
        } catch (err) {
          // Session rehydration failed, redirect to login
        }
        router.replace("/login");
      }
      setRehydrating(false);
    }

    if (!token && !user) {
      rehydrateSession();
    } else {
      setRehydrating(false);
    }
  }, [token, user, setAuth, setAvailableTenants, router]);

  if (!token || rehydrating) return null;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <AppHeader />
        <main className="flex-1 overflow-y-auto bg-background">
          <div className="mx-auto max-w-[1200px] min-h-full px-6 py-8">{children}</div>
        </main>
      </div>
    </div>
  );
}
