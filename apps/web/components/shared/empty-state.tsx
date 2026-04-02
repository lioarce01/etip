import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, description, icon, actions, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 text-center",
        className
      )}
    >
      {icon && (
        <div className="w-12 h-12 rounded-full bg-[var(--gray-100)] flex items-center justify-center mx-auto mb-4">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-medium text-foreground mt-2">{title}</h3>
      <p className="text-sm text-[var(--gray-500)] mt-1 max-w-sm mx-auto">{description}</p>
      {actions && <div className="mt-4 flex items-center gap-2">{actions}</div>}
    </div>
  );
}
