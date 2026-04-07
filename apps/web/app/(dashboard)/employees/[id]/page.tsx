"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, Code, Ticket, Building2, User } from "lucide-react";
import { addDays, format } from "date-fns";
import { useEmployee, useEmployeeAvailability } from "@/lib/hooks/use-employees";
import { PageHeader } from "@/components/shared/page-header";
import { AvatarInitials } from "@/components/shared/avatar-initials";
import { SkillBadge } from "@/components/employees/skill-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { EmployeeSkill } from "@/types/api";
import type { SkillLevel } from "@/lib/constants";

const SOURCE_ICONS: Record<string, React.ElementType> = {
  github: Code,
  jira: Ticket,
  hris: Building2,
  manual: User,
};

const SOURCE_LABELS: Record<string, string> = {
  github: "GitHub",
  jira: "Jira",
  hris: "HRIS",
  manual: "Manual",
};

function groupBySource(skills: EmployeeSkill[]): Record<string, EmployeeSkill[]> {
  return skills.reduce<Record<string, EmployeeSkill[]>>((acc, s) => {
    const src = s.source ?? "manual";
    if (!acc[src]) acc[src] = [];
    acc[src].push(s);
    return acc;
  }, {});
}

function AvailabilityBar({ pct }: { pct: number }) {
  const color =
    pct >= 60
      ? "bg-green-500"
      : pct >= 30
      ? "bg-amber-400"
      : "bg-red-500";
  return (
    <div className="h-2 w-full rounded-full bg-[var(--gray-200)]">
      <div
        className={cn("h-full rounded-full transition-all", color)}
        style={{ width: `${Math.min(pct, 100)}%` }}
      />
    </div>
  );
}

export default function EmployeeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const today = new Date();
  const startDate = format(today, "yyyy-MM-dd");
  const endDate = format(addDays(today, 90), "yyyy-MM-dd");

  const { data: employee, isLoading } = useEmployee(id);
  const { data: availability } = useEmployeeAvailability(id, startDate, endDate);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-24" />
        <div className="rounded-lg border border-[var(--gray-200)] p-5 space-y-4">
          <div className="flex items-center gap-4">
            <Skeleton className="h-12 w-12 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-4 w-32" />
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-[var(--gray-200)] p-5 space-y-3">
          <Skeleton className="h-4 w-24" />
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-20 rounded-full" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!employee) {
    return (
      <EmptyState
        title="Employee not found"
        description="This employee may have been removed or deactivated."
        actions={
          <Button variant="outline" asChild>
            <Link href="/employees">← Back to Employees</Link>
          </Button>
        }
      />
    );
  }

  const skillsBySource = groupBySource(employee.skills);
  const sources = Object.keys(skillsBySource).sort();

  return (
    <div className="space-y-6">
      {/* Back */}
      <Button variant="ghost" size="sm" asChild>
        <Link href="/employees">
          <ArrowLeft className="h-4 w-4" /> Employees
        </Link>
      </Button>

      <PageHeader title={employee.full_name} />

      {/* Identity card */}
      <div className="rounded-lg border border-[var(--gray-200)] bg-background p-5">
        <div className="flex items-center gap-4">
          <AvatarInitials name={employee.full_name} className="h-12 w-12 text-base" />
          <div className="space-y-1">
            <p className="text-base font-medium text-foreground">{employee.full_name}</p>
            <p className="text-sm text-[var(--gray-500)]">
              {employee.title ?? "—"}
              {employee.department && (
                <span> · {employee.department}</span>
              )}
            </p>
            <p className="text-xs text-[var(--gray-400)]">{employee.email}</p>
          </div>
        </div>
      </div>

      {/* Skills by source */}
      <div className="rounded-lg border border-[var(--gray-200)] bg-background p-5 space-y-5">
        <h2 className="text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
          Skills
        </h2>
        {employee.skills.length === 0 ? (
          <p className="text-sm text-[var(--gray-500)]">No skills inferred yet. Trigger a connector sync to populate skills.</p>
        ) : (
          sources.map((source) => {
            const Icon = SOURCE_ICONS[source] ?? User;
            const label = SOURCE_LABELS[source] ?? source;
            return (
              <div key={source}>
                <div className="flex items-center gap-1.5 mb-2">
                  <Icon className="h-3.5 w-3.5 text-[var(--gray-400)]" />
                  <span className="text-xs text-[var(--gray-500)]">{label}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {skillsBySource[source].map((s, i) => (
                    <SkillBadge
                      key={i}
                      label={s.skill_label}
                      level={(s.level as SkillLevel) ?? "junior"}
                    />
                  ))}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Availability */}
      <div className="rounded-lg border border-[var(--gray-200)] bg-background p-5 space-y-3">
        <h2 className="text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
          Availability (next 90 days)
        </h2>
        {availability ? (
          <>
            <AvailabilityBar pct={availability.availability_pct} />
            <div className="flex justify-between text-xs text-[var(--gray-500)]">
              <span>
                Available:{" "}
                <span className="text-foreground font-medium">
                  {availability.availability_pct.toFixed(0)}%
                </span>
              </span>
              <span>
                Allocated:{" "}
                <span className="text-foreground font-medium">
                  {availability.allocated_pct.toFixed(0)}%
                </span>
              </span>
            </div>
          </>
        ) : (
          <p className="text-sm text-[var(--gray-500)]">Availability data unavailable.</p>
        )}
      </div>
    </div>
  );
}
