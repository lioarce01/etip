import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  /** @deprecated use `actions` */
  action?: React.ReactNode;
  className?: string;
}

export function PageHeader({ title, description, actions, action, className }: PageHeaderProps) {
  const actionsSlot = actions ?? action;
  return (
    <div
      className={cn(
        "flex items-start justify-between border-b border-[var(--gray-200)] pb-6 mb-6",
        className
      )}
    >
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">{title}</h1>
        {description && (
          <p className="text-sm text-[var(--gray-500)] mt-1">{description}</p>
        )}
      </div>
      {actionsSlot && (
        <div className="flex items-center gap-2">{actionsSlot}</div>
      )}
    </div>
  );
}
