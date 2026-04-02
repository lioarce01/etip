"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listProjects,
  getProject,
  createProject,
  updateProject,
  deleteProject,
  getRecommendations,
  submitFeedback,
} from "@/lib/api/projects";

export const projectKeys = {
  all: ["projects"] as const,
  list: () => ["projects", "list"] as const,
  detail: (id: string) => ["projects", "detail", id] as const,
  recommendations: (id: string) => ["projects", "recommendations", id] as const,
};

export function useProjects() {
  return useQuery({ queryKey: projectKeys.list(), queryFn: listProjects });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: projectKeys.detail(id),
    queryFn: () => getProject(id),
    enabled: !!id,
  });
}

export function useRecommendations(projectId: string, topK = 10) {
  return useQuery({
    queryKey: projectKeys.recommendations(projectId),
    queryFn: () => getRecommendations(projectId, topK),
    enabled: !!projectId,
    staleTime: 0,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: projectKeys.all }),
  });
}

export function useUpdateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof updateProject>[1] }) =>
      updateProject(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: projectKeys.all }),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: projectKeys.all }),
  });
}

export function useSubmitFeedback(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      recommendationId,
      feedback,
    }: {
      recommendationId: string;
      feedback: Parameters<typeof submitFeedback>[2];
    }) => submitFeedback(projectId, recommendationId, feedback),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: projectKeys.recommendations(projectId) }),
  });
}
