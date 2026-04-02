import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { ConnectorStatus, ProjectStatus } from "@/lib/constants";

export function ConnectorStatusBadge({ status }: { status: ConnectorStatus }) {
  if (status === "idle") {
    return (
      <Badge variant="success">
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--green-500)]" />
          idle
        </span>
      </Badge>
    );
  }

  if (status === "syncing") {
    return (
      <Badge variant="info">
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--blue-600)] animate-pulse" />
          syncing...
        </span>
      </Badge>
    );
  }

  // error
  return (
    <Badge variant="error">
      <span className="flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--red-500)]" />
        error
      </span>
    </Badge>
  );
}

const projectStatusVariant: Record<
  ProjectStatus,
  { variant: "default" | "success" | "error" | "warning" | "info"; label: string }
> = {
  planning:  { variant: "default",  label: "Planning" },
  active:    { variant: "info",     label: "Active" },
  completed: { variant: "success",  label: "Completed" },
  on_hold:   { variant: "warning",  label: "On Hold" },
};

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  const { variant, label } = projectStatusVariant[status];
  return <Badge variant={variant}>{label}</Badge>;
}
