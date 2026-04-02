"use client";

import { format, startOfMonth, endOfMonth } from "date-fns";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { SkillBadge } from "./skill-badge";
import { AvatarInitials } from "@/components/shared/avatar-initials";
import { useEmployeeAvailability } from "@/lib/hooks/use-employees";
import { formatPct } from "@/lib/utils";
import type { Employee } from "@/types/api";

interface EmployeeDetailSheetProps {
  employee: Employee | null;
  onClose: () => void;
}

function AvailabilityBar({ pct }: { pct: number }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-[var(--gray-500)]">Available this month</span>
        <span className="text-xs font-medium text-foreground">{formatPct(pct)}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-[var(--gray-200)]">
        <div
          className="h-full rounded-full bg-[var(--blue-600)]"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

export function EmployeeDetailSheet({
  employee,
  onClose,
}: EmployeeDetailSheetProps) {
  const now = new Date();
  const startDate = format(startOfMonth(now), "yyyy-MM-dd");
  const endDate = format(endOfMonth(now), "yyyy-MM-dd");

  const { data: availability, isLoading: availLoading } =
    useEmployeeAvailability(employee?.id ?? "", startDate, endDate);

  return (
    <Sheet open={!!employee} onOpenChange={(open) => !open && onClose()}>
      <SheetContent>
        {employee && (
          <>
            <SheetHeader>
              <div className="flex items-center gap-3">
                <AvatarInitials
                  name={employee.full_name}
                  className="h-10 w-10"
                />
                <div>
                  <SheetTitle>{employee.full_name}</SheetTitle>
                  <SheetDescription>
                    {employee.title ?? "Employee"} · {employee.email}
                  </SheetDescription>
                </div>
              </div>
              {employee.department && (
                <p className="text-sm text-[var(--gray-500)]">{employee.department}</p>
              )}
            </SheetHeader>

            <div className="mt-6 space-y-6">
              {/* Skills */}
              <div>
                <h3 className="mb-2 text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
                  Skills
                </h3>
                {employee.skills.length === 0 ? (
                  <p className="text-sm text-[var(--gray-500)]">No skills recorded.</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {employee.skills.map((s, i) => (
                      <SkillBadge
                        key={i}
                        label={s.skill_label}
                        level={s.level}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Availability */}
              <div>
                <h3 className="mb-2 text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
                  Availability
                </h3>
                {availLoading ? (
                  <Skeleton className="h-6 w-full" />
                ) : availability ? (
                  <AvailabilityBar pct={availability.availability_pct} />
                ) : (
                  <p className="text-sm text-[var(--gray-500)]">
                    No availability data.
                  </p>
                )}
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
