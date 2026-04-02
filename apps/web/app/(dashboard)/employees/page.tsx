"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, Upload } from "lucide-react";
import { useEmployees } from "@/lib/hooks/use-employees";
import { useAuthStore } from "@/lib/store/auth";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { EmployeeDetailSheet } from "@/components/employees/employee-detail-sheet";
import { SkillBadge } from "@/components/employees/skill-badge";
import { AvatarInitials } from "@/components/shared/avatar-initials";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { Employee } from "@/types/api";

const PAGE_SIZE = 25;

export default function EmployeesPage() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.role === "admin";

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Employee | null>(null);

  const { data, isLoading } = useEmployees({
    page,
    page_size: PAGE_SIZE,
    search: search || undefined,
  });

  const employees = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <>
      <div className="space-y-6">
        <PageHeader
          title="Employees"
          action={
            isAdmin ? (
              <Button variant="outline" size="sm" asChild>
                <Link href="/employees/import">
                  <Upload className="h-4 w-4" /> Import CSV
                </Link>
              </Button>
            ) : undefined
          }
        />

        {/* Filters */}
        <div className="flex gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--gray-400)]" />
            <Input
              placeholder="Search by name or email..."
              className="pl-9"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>

        {/* Table */}
        <div className="rounded-lg border border-[var(--gray-200)] overflow-hidden">
          {/* Header */}
          <div className="grid grid-cols-[2fr_2fr_1fr_2fr_1fr] gap-4 border-b border-[var(--gray-200)] bg-[var(--gray-100)] px-4 py-2 text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
            <span>Name</span>
            <span>Email</span>
            <span>Department</span>
            <span>Skills</span>
            <span>Status</span>
          </div>

          {/* Body */}
          {isLoading ? (
            Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="grid grid-cols-[2fr_2fr_1fr_2fr_1fr] gap-4 border-b border-[var(--gray-200)] px-4 py-3"
              >
                {Array.from({ length: 5 }).map((_, j) => (
                  <Skeleton key={j} className="h-4 w-full" />
                ))}
              </div>
            ))
          ) : employees.length === 0 ? (
            <EmptyState
              className="border-none rounded-none"
              title="No employees yet"
              description="Import your team or run a connector sync."
              actions={
                <>
                  {isAdmin && (
                    <Button variant="outline" size="sm" asChild>
                      <Link href="/employees/import">Import CSV</Link>
                    </Button>
                  )}
                  <Button variant="outline" size="sm" asChild>
                    <Link href="/connectors">Configure Connector</Link>
                  </Button>
                </>
              }
            />
          ) : (
            employees.map((emp) => (
              <button
                key={emp.id}
                onClick={() => setSelected(emp)}
                className="grid w-full grid-cols-[2fr_2fr_1fr_2fr_1fr] gap-4 border-b border-[var(--gray-200)] px-4 py-3 text-left text-sm hover:bg-[var(--gray-50)] transition-colors last:border-b-0"
              >
                <div className="flex items-center gap-2">
                  <AvatarInitials
                    name={emp.full_name}
                    className="h-6 w-6 shrink-0"
                  />
                  <span className="truncate font-medium text-foreground">
                    {emp.full_name}
                  </span>
                </div>
                <span className="truncate text-[var(--gray-500)]">{emp.email}</span>
                <span className="truncate text-[var(--gray-500)]">
                  {emp.department ?? "—"}
                </span>
                <div className="flex items-center gap-1 flex-wrap">
                  {emp.skills.slice(0, 2).map((s, i) => (
                    <SkillBadge key={i} label={s.skill_label} level={s.level} />
                  ))}
                  {emp.skills.length > 2 && (
                    <span className="text-xs text-[var(--gray-500)]">
                      +{emp.skills.length - 2}
                    </span>
                  )}
                </div>
                <div className="flex items-center">
                  <span
                    className={
                      emp.is_active
                        ? "text-xs text-green-700"
                        : "text-xs text-[var(--gray-500)]"
                    }
                  >
                    {emp.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Pagination */}
        {total > 0 && (
          <div className="flex items-center justify-between text-sm text-[var(--gray-500)]">
            <span>
              {(page - 1) * PAGE_SIZE + 1}–
              {Math.min(page * PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                ← Prev
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </Button>
            </div>
          </div>
        )}
      </div>

      <EmployeeDetailSheet
        employee={selected}
        onClose={() => setSelected(null)}
      />
    </>
  );
}
