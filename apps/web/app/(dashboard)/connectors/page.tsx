"use client";

import { useState } from "react";
import type React from "react";
import { RefreshCw, Trash2, Plug, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import {
  useConnectors,
  useAvailableConnectors,
  useCreateConnector,
  useTriggerSync,
  useDeleteConnector,
} from "@/lib/hooks/use-connectors";
import { PageHeader } from "@/components/shared/page-header";
import { ConnectorStatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { formatRelative } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { ConnectorConfig } from "@/types/api";

// ── Connector metadata ────────────────────────────────────────────────────────

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

function JiraIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className}>
      <path d="M15.999 2C8.268 2 2 8.268 2 16s6.268 14 13.999 14C23.73 30 30 23.732 30 16S23.73 2 15.999 2z" fill="#2684FF"/>
      <path d="M22.18 15.307l-6.18-6.18-6.18 6.18 6.18 6.18 6.18-6.18z" fill="url(#jira-grad)"/>
      <path d="M16 9.127l-3.82 3.82L16 16.767l3.82-3.82L16 9.127z" fill="white" fillOpacity="0.4"/>
      <defs>
        <linearGradient id="jira-grad" x1="16" y1="9.127" x2="16" y2="22.873" gradientUnits="userSpaceOnUse">
          <stop stopColor="white" stopOpacity="0.6"/>
          <stop offset="1" stopColor="white" stopOpacity="0.1"/>
        </linearGradient>
      </defs>
    </svg>
  );
}

const CONNECTOR_META: Record<
  string,
  { icon: React.ElementType; description: string; fields: { key: string; label: string; required: boolean; type: string; placeholder?: string }[] }
> = {
  github: {
    icon: GithubIcon,
    description: "Sync engineers and infer skills from repositories, commit history, and pull request activity.",
    fields: [
      { key: "access_token", label: "Access Token", required: true,  type: "password" },
      { key: "org",          label: "Organization",  required: true,  type: "text"     },
      { key: "max_repos",    label: "Max Repos",     required: false, type: "number"   },
    ],
  },
  jira: {
    icon: JiraIcon,
    description: "Import Jira projects and infer team skills from issue assignments, labels, and components.",
    fields: [
      { key: "base_url",     label: "Jira URL",      required: true,  type: "text",     placeholder: "https://yoursite.atlassian.net" },
      { key: "email",        label: "Account Email", required: true,  type: "email",    placeholder: "you@company.com" },
      { key: "api_token",    label: "API Token",     required: true,  type: "password" },
      { key: "project_keys", label: "Project Keys",  required: false, type: "text",     placeholder: "BE, MOB (leave blank for all)" },
    ],
  },
};

function getFallbackMeta(name: string) {
  return {
    icon: Plug,
    description: `Sync employee data from ${name}.`,
    fields: [{ key: "api_key", label: "API Key", required: true, type: "password" }],
  };
}

// ── Configure dialog ──────────────────────────────────────────────────────────

function ConfigureDialog({
  connectorName,
  open,
  onOpenChange,
}: {
  connectorName: string;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { mutateAsync: createConnector, isPending } = useCreateConnector();
  const [config, setConfig] = useState<Record<string, string>>({});
  const meta = CONNECTOR_META[connectorName] ?? getFallbackMeta(connectorName);

  async function handleSave() {
    try {
      await createConnector({ connector_name: connectorName, config });
      toast.success("Connector configured");
      onOpenChange(false);
      setConfig({});
    } catch {
      toast.error("Failed to configure connector");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <meta.icon className="h-5 w-5" />
            Connect {connectorName.charAt(0).toUpperCase() + connectorName.slice(1)}
          </DialogTitle>
          <DialogDescription>{meta.description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {meta.fields.map((field) => (
            <div key={field.key} className="space-y-1.5">
              <Label htmlFor={field.key}>
                {field.label}
                {field.required && <span className="text-[var(--red-500)]"> *</span>}
              </Label>
              <Input
                id={field.key}
                type={field.type}
                placeholder={field.placeholder}
                value={config[field.key] ?? ""}
                onChange={(e) =>
                  setConfig((prev) => ({ ...prev, [field.key]: e.target.value }))
                }
              />
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleSave} disabled={isPending}>
            {isPending ? "Saving..." : "Save"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Active connector row ──────────────────────────────────────────────────────

function ActiveConnectorRow({ connector }: { connector: ConnectorConfig }) {
  const { mutate: triggerSync, isPending: syncing } = useTriggerSync();
  const { mutate: deleteConn } = useDeleteConnector();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const meta = CONNECTOR_META[connector.connector_name] ?? getFallbackMeta(connector.connector_name);
  const Icon = meta.icon;

  return (
    <>
      <div className="flex items-center gap-4 rounded-lg border border-[var(--gray-200)] bg-background px-4 py-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[var(--gray-200)] bg-[var(--gray-50)]">
          <Icon className="h-4 w-4 text-foreground" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground capitalize">{connector.connector_name}</p>
          <p className="text-xs text-[var(--gray-500)]">
            {connector.last_sync_at ? `Last sync ${formatRelative(connector.last_sync_at)}` : "Never synced"}
          </p>
        </div>
        <ConnectorStatusBadge status={connector.status} />
        <Button
          variant="outline"
          size="sm"
          onClick={() => triggerSync(connector.id, {
            onSuccess: () => toast.success("Sync triggered"),
            onError:   () => toast.error("Failed to trigger sync"),
          })}
          disabled={syncing || connector.status === "syncing"}
        >
          <RefreshCw className={cn("h-3.5 w-3.5", syncing && "animate-spin")} />
          Sync
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          className="text-[var(--red-500)] hover:text-[var(--red-500)]"
          onClick={() => setDeleteOpen(true)}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {connector.last_error && connector.status === "error" && (
        <div className="rounded border border-[var(--red-200)] bg-[var(--red-50)] px-3 py-2 text-xs text-[var(--red-500)]">
          {connector.last_error}
        </div>
      )}

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove connector?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove the {connector.connector_name} connector. Synced data will remain.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => {
              deleteConn(connector.id, {
                onSuccess: () => toast.success("Connector removed"),
                onError:   () => toast.error("Failed to remove connector"),
              });
              setDeleteOpen(false);
            }}>
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

// ── Catalog card ──────────────────────────────────────────────────────────────

function CatalogCard({
  name,
  isConfigured,
  onConnect,
}: {
  name: string;
  isConfigured: boolean;
  onConnect: () => void;
}) {
  const meta = CONNECTOR_META[name] ?? getFallbackMeta(name);
  const Icon = meta.icon;

  return (
    <div className={cn(
      "flex flex-col gap-4 rounded-lg border bg-background p-5 transition-colors",
      isConfigured
        ? "border-[var(--gray-200)] opacity-60"
        : "border-[var(--gray-200)] hover:border-[var(--gray-300)]"
    )}>
      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--gray-200)] bg-[var(--gray-50)]">
          <Icon className="h-5 w-5 text-foreground" />
        </div>
        {isConfigured && (
          <span className="text-xs text-[var(--gray-500)] border border-[var(--gray-200)] rounded-full px-2 py-0.5">
            Connected
          </span>
        )}
      </div>
      <div>
        <p className="text-sm font-medium text-foreground capitalize">{name}</p>
        <p className="mt-1 text-xs text-[var(--gray-500)] leading-relaxed">{meta.description}</p>
      </div>
      <Button
        variant={isConfigured ? "outline" : "secondary"}
        size="sm"
        className="mt-auto w-full justify-between"
        disabled={isConfigured}
        onClick={onConnect}
      >
        {isConfigured ? "Already connected" : "Connect"}
        {!isConfigured && <ChevronRight className="h-3.5 w-3.5" />}
      </Button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ConnectorsPage() {
  const { data: connectors, isLoading: loadingActive } = useConnectors();
  const { data: available, isLoading: loadingAvailable } = useAvailableConnectors();
  const [configuringName, setConfiguringName] = useState<string | null>(null);

  const configuredNames = new Set(connectors?.map((c) => c.connector_name) ?? []);

  return (
    <>
      <div className="space-y-8">
        <PageHeader title="Connectors" />

        {/* Active connectors */}
        {(loadingActive || (connectors && connectors.length > 0)) && (
          <section className="space-y-3">
            <h2 className="text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
              Active
            </h2>
            {loadingActive ? (
              <Skeleton className="h-16 w-full" />
            ) : (
              <div className="space-y-2">
                {connectors!.map((c) => (
                  <ActiveConnectorRow key={c.id} connector={c} />
                ))}
              </div>
            )}
          </section>
        )}

        {/* Catalog */}
        <section className="space-y-3">
          <h2 className="text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
            Available Integrations
          </h2>
          {loadingAvailable ? (
            <div className="grid grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-44 w-full" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              {(available ?? []).map((name) => (
                <CatalogCard
                  key={name}
                  name={name}
                  isConfigured={configuredNames.has(name)}
                  onConnect={() => setConfiguringName(name)}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      {configuringName && (
        <ConfigureDialog
          connectorName={configuringName}
          open={!!configuringName}
          onOpenChange={(v) => !v && setConfiguringName(null)}
        />
      )}
    </>
  );
}
