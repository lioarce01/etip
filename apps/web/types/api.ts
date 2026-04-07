import type { Role, SkillLevel, ProjectStatus, ConnectorStatus, FeedbackValue } from "@/lib/constants";

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface User {
  id: string;
  email: string;
  role: Role;
  tenant_id: string;
  is_platform_admin: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface LoginResponse {
  access_token?: string;
  token_type?: string;
  pre_auth_token?: string;
  tenants?: Tenant[];
}

// ── Employees ─────────────────────────────────────────────────────────────────

export interface EmployeeSkill {
  skill_label: string;
  level: SkillLevel;
  source: string;
  esco_uri?: string;
}

export interface Employee {
  id: string;
  email: string;
  full_name: string;
  title?: string;
  department?: string;
  source?: string;
  is_active: boolean;
  tenant_id?: string;
  created_at?: string;
  skills: EmployeeSkill[];
}

export interface EmployeeAvailability {
  employee_id: string;
  capacity_pct: number;
  allocated_pct: number;
  availability_pct: number;
}

export interface EmployeeListResponse {
  items: Employee[];
  total: number;
  page: number;
  page_size: number;
}

export interface CSVImportResult {
  created: number;
  updated: number;
  errors: Array<{ row: number; message: string }>;
}

// ── Projects ──────────────────────────────────────────────────────────────────

export interface SkillRequirement {
  skill_label: string;
  level: SkillLevel;
  weight: number;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  start_date?: string;
  end_date?: string;
  status: ProjectStatus;
  required_skills: SkillRequirement[];
  tenant_id?: string;
  created_at?: string;
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
}

// ── Recommendations ───────────────────────────────────────────────────────────

export interface SkillMatch {
  skill_label: string;
  required_level: SkillLevel;
  matched: boolean;
}

export interface RecommendationEmployee {
  id: string;
  email: string;
  full_name: string;
  title?: string;
  department?: string;
  is_active: boolean;
}

export interface Recommendation {
  id: string;
  employee: RecommendationEmployee;
  score: number;
  skill_matches: SkillMatch[];
  explanation: string;
  availability_pct: number;
  feedback?: FeedbackValue;
}

// ── Connectors ────────────────────────────────────────────────────────────────

export interface ConnectorConfig {
  id: string;
  connector_name: string;
  config: Record<string, unknown>;
  is_active: boolean;
  status: ConnectorStatus;
  last_sync_at?: string;
  last_error?: string;
  tenant_id: string;
  created_at: string;
}

export interface ConnectorSchema {
  name: string;
  config_schema: {
    type: string;
    properties: Record<string, { type: string; title?: string; description?: string; default?: unknown }>;
    required?: string[];
  };
}

// ── Analytics ────────────────────────────────────────────────────────────────

export interface Analytics {
  total_employees: number;
  total_projects: number;
  total_recommendations: number;
  accepted_count: number;
  rejected_count: number;
  maybe_count: number;
  no_feedback_count: number;
  precision_at_5: number;
  precision_at_10: number;
  acceptance_rate: number;
}

// ── Pagination ────────────────────────────────────────────────────────────────

export interface PaginationParams {
  page?: number;
  page_size?: number;
  search?: string;
}
