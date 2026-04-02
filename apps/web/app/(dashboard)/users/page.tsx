"use client";

import { useState } from "react";
import { Plus, Trash2, MoreHorizontal } from "lucide-react";
import { toast } from "sonner";
import { useUsers, useCreateUser, useDeleteUser, useUpdateUser } from "@/lib/hooks/use-users";
import { useAuthStore } from "@/lib/store/auth";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { AvatarInitials } from "@/components/shared/avatar-initials";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ROLES, type Role } from "@/lib/constants";
import type { User } from "@/types/api";

type BadgeVariant = "default" | "success" | "error" | "warning" | "info";

const ROLE_LABEL: Record<Role, string> = {
  admin: "Admin",
  tm:    "Tech Manager",
  dev:   "Developer",
};

const roleVariant: Record<Role, BadgeVariant> = {
  admin: "warning",
  tm:    "info",
  dev:   "default",
};

function InviteDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { mutateAsync, isPending } = useCreateUser();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("tm");

  async function handleInvite() {
    try {
      await mutateAsync({ email, password, role });
      toast.success("User invited");
      onOpenChange(false);
      setEmail("");
      setPassword("");
    } catch {
      toast.error("Failed to invite user");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite Team Member</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Email</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@acme.com"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Temporary password</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Role</Label>
            <Select defaultValue={role} onValueChange={(v) => setRole(v as Role)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r} value={r}>
                    {ROLE_LABEL[r]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleInvite}
            disabled={isPending || !email || !password}
          >
            {isPending ? "Inviting..." : "Invite"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function UsersPage() {
  const { data: users, isLoading } = useUsers();
  const { mutate: deleteUser } = useDeleteUser();
  const { mutate: updateUser } = useUpdateUser();
  const currentUser = useAuthStore((s) => s.user);

  const [inviteOpen, setInviteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);

  return (
    <>
      <div className="space-y-6">
        <PageHeader
          title="Team"
          action={
            <Button size="sm" onClick={() => setInviteOpen(true)}>
              <Plus className="h-4 w-4" /> Invite Member
            </Button>
          }
        />

        <div className="rounded-lg border border-[var(--gray-200)] overflow-hidden">
          <div className="grid grid-cols-[2fr_2fr_1fr_1fr_auto] gap-4 border-b border-[var(--gray-200)] bg-[var(--gray-100)] px-4 py-2 text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
            <span>Name</span>
            <span>Email</span>
            <span>Role</span>
            <span className="text-center">Status</span>
            <span />
          </div>

          {isLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="grid grid-cols-[2fr_2fr_1fr_1fr_auto] gap-4 border-b border-[var(--gray-200)] px-4 py-3"
              >
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-8" />
              </div>
            ))
          ) : !users || users.length === 0 ? (
            <EmptyState
              className="border-none rounded-none"
              title="You're the only one here"
              description="Invite your team."
              actions={
                <Button size="sm" onClick={() => setInviteOpen(true)}>
                  <Plus className="h-4 w-4" /> Invite Member
                </Button>
              }
            />
          ) : (
            users.map((u) => (
              <div
                key={u.id}
                className="grid grid-cols-[2fr_2fr_1fr_1fr_auto] gap-4 items-center border-b border-[var(--gray-200)] px-4 py-3 last:border-b-0"
              >
                <div className="flex items-center gap-2">
                  <AvatarInitials
                    name={u.email.split("@")[0]}
                    className="h-6 w-6"
                  />
                  <span className="text-sm text-foreground truncate">
                    {u.email.split("@")[0]}
                  </span>
                </div>
                <span className="text-sm text-[var(--gray-500)] truncate">
                  {u.email}
                </span>
                <div><Badge variant={roleVariant[u.role]}>{ROLE_LABEL[u.role]}</Badge></div>
                <div className="flex justify-center"><span className="text-xs text-green-700">Active</span></div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon-sm">
                      <MoreHorizontal className="h-4 w-4 text-[var(--gray-500)]" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() =>
                        updateUser(
                          {
                            id: u.id,
                            payload: {
                              role: u.role === "admin" ? "tm" : "admin",
                            },
                          },
                          {
                            onSuccess: () =>
                              toast.success("Role updated"),
                            onError: () =>
                              toast.error("Failed to update role"),
                          }
                        )
                      }
                    >
                      Toggle role
                    </DropdownMenuItem>
                    {u.id !== currentUser?.id && (
                      <DropdownMenuItem
                        className="text-[var(--red-500)] focus:text-[var(--red-500)]"
                        onClick={() => setDeleteTarget(u)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" /> Delete
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ))
          )}
        </div>
      </div>

      <InviteDialog open={inviteOpen} onOpenChange={setInviteOpen} />

      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete user?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete{" "}
              <strong>{deleteTarget?.email}</strong>.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!deleteTarget) return;
                deleteUser(deleteTarget.id, {
                  onSuccess: () => toast.success("User deleted"),
                  onError: () => toast.error("Failed to delete user"),
                });
                setDeleteTarget(null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
