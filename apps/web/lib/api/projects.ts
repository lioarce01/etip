import { apiClient } from "./client";
import type { Project, ProjectListResponse, Recommendation } from "@/types/api";
import type { ProjectStatus, SkillLevel } from "@/lib/constants";

export async function listProjects(): Promise<ProjectListResponse> {
  return apiClient.get("api/v1/projects").json<ProjectListResponse>();
}

export async function getProject(id: string): Promise<Project> {
  return apiClient.get(`api/v1/projects/${id}`).json<Project>();
}

export interface CreateProjectPayload {
  name: string;
  description?: string;
  start_date?: string;
  end_date?: string;
  status: ProjectStatus;
  required_skills: Array<{
    skill_label: string;
    level: SkillLevel;
    weight: number;
  }>;
}

export async function createProject(payload: CreateProjectPayload): Promise<Project> {
  return apiClient
    .post("api/v1/projects", { json: payload })
    .json<Project>();
}

export async function updateProject(
  id: string,
  payload: Partial<CreateProjectPayload>
): Promise<Project> {
  return apiClient
    .patch(`api/v1/projects/${id}`, { json: payload })
    .json<Project>();
}

export async function deleteProject(id: string): Promise<void> {
  await apiClient.delete(`api/v1/projects/${id}`);
}

export async function getRecommendations(
  projectId: string,
  topK = 10
): Promise<Recommendation[]> {
  return apiClient
    .get(`api/v1/projects/${projectId}/recommendations`, {
      searchParams: { top_k: topK },
    })
    .json<Recommendation[]>();
}

export async function submitFeedback(
  projectId: string,
  recommendationId: string,
  feedback: "accepted" | "maybe" | "rejected"
): Promise<void> {
  await apiClient.post(
    `api/v1/projects/${projectId}/recommendations/${recommendationId}/feedback`,
    { json: { feedback } }
  );
}
