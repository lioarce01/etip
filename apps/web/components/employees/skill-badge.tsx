import { cn } from "@/lib/utils";
import type { SkillLevel } from "@/lib/constants";

const levelColors: Record<SkillLevel, string> = {
  junior: "border-[var(--gray-200)] text-[var(--gray-500)]",
  mid:    "border-[var(--blue-600)]/30 text-[var(--blue-600)]",
  senior: "border-green-600/30 text-green-700",
};

interface SkillBadgeProps {
  label: string;
  level: SkillLevel;
  className?: string;
}

export function SkillBadge({ label, level, className }: SkillBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs",
        levelColors[level],
        className
      )}
    >
      {label}
      <span className="ml-1 opacity-60">{level}</span>
    </span>
  );
}
