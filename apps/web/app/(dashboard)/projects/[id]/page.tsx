"use client";

import { use } from "react";
import Link from "next/link";
import { RefreshCw, ArrowLeft } from "lucide-react";
import {
  useProject,
  useRecommendations,
  useSubmitFeedback,
} from "@/lib/hooks/use-projects";
import { PageHeader } from "@/components/shared/page-header";
import { ProjectStatusBadge } from "@/components/shared/status-badge";
import { CandidateMatchCard } from "@/components/recommendations/candidate-match-card";
import { SkillBadge } from "@/components/employees/skill-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/utils";
import type { FeedbackValue } from "@/lib/constants";

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const { data: project, isLoading: projLoading } = useProject(id);
  const {
    data: recs,
    isLoading: recsLoading,
    refetch,
    isFetching,
  } = useRecommendations(id);
  const { mutateAsync: submitFeedback } = useSubmitFeedback(id);

  async function handleFeedback(recommendationId: string, feedback: FeedbackValue, reason?: string) {
    await submitFeedback({ recommendationId, feedback, reason });
  }

  if (projLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!project) {
    return (
      <EmptyState
        title="Project not found"
        description="This project may have been deleted."
        actions={
          <Button variant="outline" asChild>
            <Link href="/projects">← Back to Projects</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/projects">
            <ArrowLeft className="h-4 w-4" /> Projects
          </Link>
        </Button>
      </div>

      {/* Project info card */}
      <div className="rounded-lg border border-[var(--gray-200)] bg-background p-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold text-foreground">
                {project.name}
              </h1>
              <ProjectStatusBadge status={project.status} />
            </div>
            {project.description && (
              <p className="mt-1 text-sm text-[var(--gray-500)]">
                {project.description}
              </p>
            )}
            {(project.start_date || project.end_date) && (
              <p className="mt-1 text-xs text-[var(--gray-500)]">
                {project.start_date && formatDate(project.start_date)}
                {project.start_date && project.end_date && " → "}
                {project.end_date && formatDate(project.end_date)}
              </p>
            )}
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link href={`/projects/${id}?edit=1`}>Edit</Link>
          </Button>
        </div>

        {project.required_skills.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs text-[var(--gray-500)] uppercase tracking-wider">
              Required
            </p>
            <div className="flex flex-wrap gap-1.5">
              {project.required_skills.map((s, i) => (
                <SkillBadge
                  key={i}
                  label={s.skill_label}
                  level={s.level}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Recommendations */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-medium text-foreground">
            Recommended Candidates
          </h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw
              className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>

        {recsLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-48 w-full" />
            ))}
          </div>
        ) : !recs || recs.length === 0 ? (
          <EmptyState
            title="No candidates match yet"
            description="Make sure employees have been synced and have skills assigned."
            actions={
              <Button variant="outline" size="sm" asChild>
                <Link href="/connectors">Go to Connectors</Link>
              </Button>
            }
          />
        ) : (
          <div className="space-y-4">
            {recs.map((rec, i) => (
              <CandidateMatchCard
                key={rec.employee.id}
                rec={rec}
                rank={i + 1}
                onFeedback={handleFeedback}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
