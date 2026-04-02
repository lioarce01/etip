"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useCreateProject } from "@/lib/hooks/use-projects";
import { ProjectForm } from "@/components/projects/project-form";
import { PageHeader } from "@/components/shared/page-header";

export default function NewProjectPage() {
  const router = useRouter();
  const { mutateAsync, isPending } = useCreateProject();

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="New Project" />

      <div className="rounded-lg border border-[var(--gray-200)] bg-background p-6">
        <ProjectForm
          onSubmit={async (data) => {
            try {
              const project = await mutateAsync(data);
              toast.success("Project created");
              router.push(`/projects/${project.id}`);
            } catch {
              toast.error("Failed to create project");
            }
          }}
          onCancel={() => router.push("/projects")}
          isLoading={isPending}
        />
      </div>
    </div>
  );
}
