// API calls go through the Next.js proxy (rewrites in next.config.ts).
// The browser calls same-origin paths like /auth/login — no CORS needed.
// NEXT_PUBLIC_API_URL is no longer required.
export const API_BASE_URL = "/";

export const ROLES = ["admin", "tm", "dev"] as const;
export type Role = (typeof ROLES)[number];

export const SKILL_LEVELS = ["junior", "mid", "senior"] as const;
export type SkillLevel = (typeof SKILL_LEVELS)[number];

export const PROJECT_STATUSES = [
  "planning",
  "active",
  "completed",
  "on_hold",
] as const;
export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

export const CONNECTOR_STATUSES = ["idle", "syncing", "error"] as const;
export type ConnectorStatus = (typeof CONNECTOR_STATUSES)[number];

export const FEEDBACK_VALUES = ["accepted", "maybe", "rejected"] as const;
export type FeedbackValue = (typeof FEEDBACK_VALUES)[number];
