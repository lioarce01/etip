"use client";

import Link from "next/link";
import { Users, FolderKanban, Plug, Plus, Upload } from "lucide-react";
import { useEmployees } from "@/lib/hooks/use-employees";
import { useProjects } from "@/lib/hooks/use-projects";
import { useConnectors } from "@/lib/hooks/use-connectors";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { ConnectorStatusBadge } from "@/components/shared/status-badge";
import { formatRelative } from "@/lib/utils";

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
}) {
  return (
    <div className="rounded-lg border border-[var(--gray-200)] bg-background p-5">
      <div className="flex items-center justify-between">
        <p className="text-xs text-[var(--gray-500)] uppercase tracking-wider">{label}</p>
        <Icon className="h-4 w-4 text-[var(--gray-300)]" />
      </div>
      <p className="mt-3 text-2xl font-semibold tabular-nums text-foreground">
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-[var(--gray-500)]">{sub}</p>}
    </div>
  );
}

export default function OverviewPage() {
  const { data: employees } = useEmployees({ page_size: 1 });
  const { data: projects } = useProjects();
  const { data: connectors } = useConnectors();

  const activeProjects = projects?.items.filter(
    (p) => p.status === "active"
  ).length ?? 0;

  const activeConnectors = connectors?.filter((c) => c.is_active).length ?? 0;
  const lastSync = connectors
    ?.filter((c) => c.last_sync_at)
    .sort(
      (a, b) =>
        new Date(b.last_sync_at!).getTime() - new Date(a.last_sync_at!).getTime()
    )[0];

  return (
    <div className="space-y-8">
      <PageHeader title="Overview" />

      {/* KPI Row */}
      <div className="grid grid-cols-3 gap-4">
        <KpiCard
          label="Employees"
          value={employees?.total ?? "—"}
          icon={Users}
        />
        <KpiCard
          label="Active Projects"
          value={activeProjects}
          icon={FolderKanban}
        />
        <KpiCard
          label="Connectors"
          value={`${activeConnectors} active`}
          sub={
            lastSync?.last_sync_at
              ? `Last sync ${formatRelative(lastSync.last_sync_at)}`
              : "No syncs yet"
          }
          icon={Plug}
        />
      </div>

      {/* Recent connector activity */}
      <div>
        <h2 className="mb-3 text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
          Recent Activity
        </h2>
        <div className="rounded-lg border border-[var(--gray-200)] divide-y divide-[var(--gray-200)]">
          {!connectors || connectors.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--gray-500)]">
              No connector syncs yet.{" "}
              <Link href="/connectors" className="text-[var(--blue-600)] hover:underline">
                Configure a connector
              </Link>
            </div>
          ) : (
            connectors.slice(0, 5).map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {c.connector_name}
                  </p>
                  <p className="text-xs text-[var(--gray-500)]">
                    {c.last_sync_at
                      ? formatRelative(c.last_sync_at)
                      : "Never synced"}
                  </p>
                </div>
                <ConnectorStatusBadge status={c.status} />
              </div>
            ))
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="mb-3 text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
          Quick Actions
        </h2>
        <div className="flex gap-3">
          <Button variant="outline" asChild>
            <Link href="/projects/new">
              <Plus className="h-4 w-4" /> New Project
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/employees/import">
              <Upload className="h-4 w-4" /> Import Employees
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/connectors">
              <Plug className="h-4 w-4" /> Configure Connector
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
