"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  TrendingUp,
  Users,
  FolderKanban,
  Plug,
  Settings,
  UsersRound,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Building2,
  ChevronsUpDown,
  Check,
} from "lucide-react";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/store/auth";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { switchTenant } from "@/lib/api/auth";
import { getMe, getMyTenants } from "@/lib/api/auth";

const mainNav = [
  { href: "/overview",   label: "Overview",    icon: LayoutDashboard },
  { href: "/employees",  label: "Employees",   icon: Users },
  { href: "/projects",   label: "Projects",    icon: FolderKanban },
  { href: "/analytics",  label: "Analytics",   icon: TrendingUp },
  { href: "/connectors", label: "Connectors",  icon: Plug, adminOnly: true },
];

const secondaryNav = [
  { href: "/users",    label: "Team",     icon: UsersRound, adminOnly: true },
  { href: "/settings", label: "Settings", icon: Settings },
];

function NavItem({
  href,
  label,
  icon: Icon,
  adminOnly,
  isAdmin,
  pathname,
  collapsed,
}: {
  href: string;
  label: string;
  icon: React.ElementType;
  adminOnly?: boolean;
  isAdmin: boolean;
  pathname: string;
  collapsed: boolean;
}) {
  if (adminOnly && !isAdmin) return null;
  const active = pathname === href || pathname.startsWith(href + "/");
  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={cn(
        "flex items-center rounded-md px-3 py-2 text-sm transition-colors duration-150",
        collapsed ? "justify-center gap-0" : "gap-2.5",
        active
          ? "bg-[var(--gray-100)] text-foreground font-medium"
          : "text-[var(--gray-500)] hover:bg-[var(--gray-100)] hover:text-foreground"
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </Link>
  );
}

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, token, tenant, availableTenants, clearAuth, setAuth, setAvailableTenants } = useAuthStore();
  const queryClient = useQueryClient();
  const [collapsed, setCollapsed] = useState(false);
  const [switchingTenant, setSwitchingTenant] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("sidebar-collapsed");
    if (stored === "true") setCollapsed(true);
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      localStorage.setItem("sidebar-collapsed", String(!prev));
      return !prev;
    });
  }

  function handleLogout() {
    clearAuth();
    router.push("/login");
  }

  async function handleSwitchTenant(t: any) {
    if (!user || !token) return;
    setSwitchingTenant(true);
    try {
      const response = await switchTenant(t.id, token);
      const updatedUser = await getMe(response.access_token);
      const myTenants = await getMyTenants(response.access_token);
      setAvailableTenants(myTenants);
      setAuth(response.access_token, updatedUser, t);
      queryClient.invalidateQueries();
      // Stay on current route — the RLS context will auto-update via middleware
    } catch {
      toast.error("Failed to switch workspace.");
    } finally {
      setSwitchingTenant(false);
    }
  }

  const isAdmin = user?.role === "admin";
  const initials = (user?.email?.split("@")[0] ?? "U").slice(0, 2).toUpperCase();

  return (
    <aside
      className={cn(
        "relative flex shrink-0 flex-col border-r border-[var(--gray-200)] bg-background transition-all duration-200",
        collapsed ? "w-14" : "w-60"
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center border-b border-[var(--gray-200)] px-4">
        {collapsed ? (
          <span className="mx-auto text-sm font-semibold text-foreground">◆</span>
        ) : (
          <span className="text-sm font-semibold tracking-tight text-foreground">◆ ETIP</span>
        )}
      </div>

      {/* Collapse toggle */}
      <button
        onClick={toggleCollapsed}
        className="absolute -right-3 top-[52px] z-10 flex h-6 w-6 items-center justify-center rounded-full border border-[var(--gray-200)] bg-background text-[var(--gray-500)] hover:text-foreground transition-colors"
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? (
          <ChevronRight className="h-3 w-3" />
        ) : (
          <ChevronLeft className="h-3 w-3" />
        )}
      </button>

      {/* Main nav */}
      <nav className="flex flex-1 flex-col gap-0.5 p-2">
        {mainNav.map((item) => (
          <NavItem
            key={item.href}
            {...item}
            isAdmin={isAdmin}
            pathname={pathname}
            collapsed={collapsed}
          />
        ))}

        <div className="my-2 border-t border-[var(--gray-200)]" />

        {secondaryNav.map((item) => (
          <NavItem
            key={item.href}
            {...item}
            isAdmin={isAdmin}
            pathname={pathname}
            collapsed={collapsed}
          />
        ))}
      </nav>

      {/* User footer */}
      <div className="border-t border-[var(--gray-200)] p-2">
        {/* Tenant switcher (multi-tenant only) */}
        {availableTenants.length > 1 && !collapsed && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="w-full flex items-center gap-2 rounded-md border border-[var(--gray-200)] bg-background px-2 py-1.5 text-xs font-medium text-foreground hover:bg-[var(--gray-100)] mb-2 transition-colors">
                <Building2 className="h-3 w-3 shrink-0" />
                <span className="truncate flex-1 text-left">{tenant?.name}</span>
                <ChevronsUpDown className="h-3 w-3 shrink-0" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {availableTenants.map((t) => (
                <DropdownMenuItem
                  key={t.id}
                  onClick={() => handleSwitchTenant(t)}
                  disabled={switchingTenant}
                  className="text-foreground"
                >
                  <span>{t.name}</span>
                  {t.id === tenant?.id && <Check className="ml-auto h-3.5 w-3.5" />}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        {collapsed ? (
          <div className="flex flex-col items-center gap-1">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--gray-900)] text-[10px] font-semibold text-white">
              {initials}
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={handleLogout}
              title="Log out"
            >
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2.5 rounded-md px-2 py-1.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--gray-900)] text-[10px] font-semibold text-white">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-foreground">{user?.email}</p>
              <p className="truncate text-xs text-[var(--gray-500)]">{tenant?.slug}</p>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={handleLogout}
              title="Log out"
              className="shrink-0"
            >
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>
    </aside>
  );
}
