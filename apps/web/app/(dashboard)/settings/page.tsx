"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getMyTenant, updateTenant } from "@/lib/api/tenants";
import { changePassword } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/auth";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function SettingsPage() {
  const token = useAuthStore((s) => s.token);
  const { data: tenant, refetch } = useQuery({
    queryKey: ["tenant", "me"],
    queryFn: getMyTenant,
  });

  // Workspace form
  const [tenantName, setTenantName] = useState(tenant?.name ?? "");
  const { mutate: saveTenant, isPending: savingTenant } = useMutation({
    mutationFn: () => updateTenant({ name: tenantName }),
    onSuccess: () => {
      toast.success("Workspace updated");
      refetch();
    },
    onError: () => toast.error("Failed to update workspace"),
  });

  // Password form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const { mutate: savePassword, isPending: savingPassword } = useMutation({
    mutationFn: () => changePassword(currentPassword, newPassword, token ?? ""),
    onSuccess: () => {
      toast.success("Password updated");
      setCurrentPassword("");
      setNewPassword("");
    },
    onError: () => toast.error("Failed to update password"),
  });

  return (
    <div className="space-y-6 max-w-2xl">
      <PageHeader title="Settings" />

      <Tabs defaultValue="workspace">
        <TabsList>
          <TabsTrigger value="workspace">Workspace</TabsTrigger>
          <TabsTrigger value="account">Account</TabsTrigger>
        </TabsList>

        <TabsContent value="workspace">
          <div className="mt-4 rounded-lg border border-[var(--gray-200)] bg-background p-6 space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="tenant-name">Company name</Label>
              <Input
                id="tenant-name"
                value={tenantName || tenant?.name || ""}
                onChange={(e) => setTenantName(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Workspace slug</Label>
              <Input value={tenant?.slug ?? ""} disabled />
              <p className="text-xs text-[var(--gray-500)]">
                Slug cannot be changed after creation.
              </p>
            </div>
            <div className="border-t border-[var(--gray-200)]" />
            <Button
              onClick={() => saveTenant()}
              disabled={savingTenant}
            >
              {savingTenant ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="account">
          <div className="mt-4 rounded-lg border border-[var(--gray-200)] bg-background p-6 space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="current-pass">Current password</Label>
              <Input
                id="current-pass"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-pass">New password</Label>
              <Input
                id="new-pass"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
            <div className="border-t border-[var(--gray-200)]" />
            <Button
              onClick={() => savePassword()}
              disabled={
                savingPassword || !currentPassword || !newPassword
              }
            >
              {savingPassword ? "Updating..." : "Update Password"}
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
