"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Pencil } from "lucide-react";
import { toast } from "sonner";
import { useProjects, useCreateProject, useDeleteProject } from "@/lib/hooks/use-projects";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { ProjectStatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { SkillBadge } from "@/components/employees/skill-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ProjectForm } from "@/components/projects/project-form";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export default function ProjectsPage() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useProjects();
  const { mutateAsync: createProject, isPending: creating } = useCreateProject();
  const { mutate: deleteProject } = useDeleteProject();

  const projects = data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Projects"
        action={
          <Button size="sm" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> New Project
          </Button>
        }
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>New Project</DialogTitle>
          </DialogHeader>
          <ProjectForm
            onSubmit={async (data) => {
              try {
                const project = await createProject(data);
                toast.success("Project created");
                setOpen(false);
                router.push(`/projects/${project.id}`);
              } catch {
                toast.error("Failed to create project");
              }
            }}
            onCancel={() => setOpen(false)}
            isLoading={creating}
          />
        </DialogContent>
      </Dialog>

      <div className="rounded-lg border border-[var(--gray-200)] overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-[2fr_1fr_3fr_auto] gap-4 border-b border-[var(--gray-200)] bg-[var(--gray-100)] px-4 py-2 text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
          <span>Name</span>
          <span>Status</span>
          <span>Required Skills</span>
          <span />
        </div>

        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="grid grid-cols-[2fr_1fr_3fr_auto] gap-4 border-b border-[var(--gray-200)] px-4 py-3"
            >
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-16" />
            </div>
          ))
        ) : projects.length === 0 ? (
          <EmptyState
            className="border-none rounded-none"
            title="No projects yet"
            description="Create your first project to get recommendations."
            actions={
              <Button size="sm" onClick={() => setOpen(true)}>
                <Plus className="h-4 w-4" /> New Project
              </Button>
            }
          />
        ) : (
          projects.map((project) => (
            <div
              key={project.id}
              className="grid grid-cols-[2fr_1fr_3fr_auto] gap-4 items-center border-b border-[var(--gray-200)] px-4 py-3 last:border-b-0 hover:bg-[var(--gray-50)] transition-colors"
            >
              <button
                className="text-left text-sm font-medium text-foreground hover:text-[var(--blue-600)] transition-colors"
                onClick={() => router.push(`/projects/${project.id}`)}
              >
                {project.name}
              </button>

              <div><ProjectStatusBadge status={project.status} /></div>

              <div className="flex items-center gap-1 flex-wrap">
                {project.required_skills.slice(0, 3).map((s, i) => (
                  <SkillBadge key={i} label={s.skill_label} level={s.level} />
                ))}
                {project.required_skills.length > 3 && (
                  <span className="text-xs text-[var(--gray-500)]">
                    +{project.required_skills.length - 3}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" asChild>
                  <Link href={`/projects/${project.id}`}>View</Link>
                </Button>

                <AlertDialog>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon-sm">
                        <span className="text-[var(--gray-500)]">•••</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        className="text-foreground"
                        onClick={() => router.push(`/projects/${project.id}?edit=1`)}
                      >
                        <Pencil className="mr-2 h-4 w-4" /> Edit
                      </DropdownMenuItem>
                      <AlertDialogTrigger asChild>
                        <DropdownMenuItem className="text-[var(--red-500)] focus:text-[var(--red-500)]">
                          <Trash2 className="mr-2 h-4 w-4" /> Delete
                        </DropdownMenuItem>
                      </AlertDialogTrigger>
                    </DropdownMenuContent>
                  </DropdownMenu>

                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete project?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will permanently delete &ldquo;{project.name}&rdquo; and all
                        associated data. This cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => {
                          deleteProject(project.id, {
                            onSuccess: () => toast.success("Project deleted"),
                            onError: () => toast.error("Failed to delete project"),
                          });
                        }}
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
