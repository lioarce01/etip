import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "success" | "error" | "warning" | "info";

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-[var(--gray-100)] text-[var(--gray-600)]",
  success: "bg-[var(--green-100)] text-green-700",
  error:   "bg-[var(--red-100)] text-[var(--red-500)]",
  warning: "bg-amber-100 text-amber-700",
  info:    "bg-blue-100 text-[var(--blue-600)]",
};

export function Badge({
  variant = "default",
  className,
  children,
}: {
  variant?: BadgeVariant;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variantClasses[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
