/* ── Enums — mirror backend exactly ─────────────────────────────────── */

export const UserRole = {
  EMPLOYEE: "EMPLOYEE",
  MANAGER: "MANAGER",
  ADMIN: "ADMIN",
} as const;
export type UserRole = (typeof UserRole)[keyof typeof UserRole];

export const GoalStatus = {
  DRAFT: "DRAFT",
  SUBMITTED: "SUBMITTED",
  APPROVED: "APPROVED",
  RETURNED: "RETURNED",
  LOCKED: "LOCKED",
} as const;
export type GoalStatus = (typeof GoalStatus)[keyof typeof GoalStatus];

export const UomType = {
  NUMERIC_MIN: "NUMERIC_MIN",
  NUMERIC_MAX: "NUMERIC_MAX",
  PERCENTAGE_MIN: "PERCENTAGE_MIN",
  PERCENTAGE_MAX: "PERCENTAGE_MAX",
  TIMELINE: "TIMELINE",
  ZERO: "ZERO",
} as const;
export type UomType = (typeof UomType)[keyof typeof UomType];

export const Quarter = {
  Q1: "Q1",
  Q2: "Q2",
  Q3: "Q3",
  Q4: "Q4",
} as const;
export type Quarter = (typeof Quarter)[keyof typeof Quarter];

export const GoalProgress = {
  NOT_STARTED: "NOT_STARTED",
  ON_TRACK: "ON_TRACK",
  COMPLETED: "COMPLETED",
} as const;
export type GoalProgress = (typeof GoalProgress)[keyof typeof GoalProgress];

export const CycleStatus = {
  ACTIVE: "ACTIVE",
  CLOSED: "CLOSED",
} as const;
export type CycleStatus = (typeof CycleStatus)[keyof typeof CycleStatus];

export const EscalationEventType = {
  GOALS_NOT_SUBMITTED: "GOALS_NOT_SUBMITTED",
  MANAGER_NOT_APPROVED: "MANAGER_NOT_APPROVED",
  CHECKIN_NOT_COMPLETED: "CHECKIN_NOT_COMPLETED",
} as const;
export type EscalationEventType =
  (typeof EscalationEventType)[keyof typeof EscalationEventType];

export const EscalationStatus = {
  OPEN: "OPEN",
  RESOLVED: "RESOLVED",
} as const;
export type EscalationStatus =
  (typeof EscalationStatus)[keyof typeof EscalationStatus];

export const NotificationChannel = {
  EMAIL: "EMAIL",
  TEAMS: "TEAMS",
} as const;
export type NotificationChannel =
  (typeof NotificationChannel)[keyof typeof NotificationChannel];

export const NotificationEventType = {
  GOAL_SUBMITTED: "GOAL_SUBMITTED",
  GOAL_APPROVED: "GOAL_APPROVED",
  GOAL_RETURNED: "GOAL_RETURNED",
  GOAL_LOCKED: "GOAL_LOCKED",
  ESCALATION_RAISED: "ESCALATION_RAISED",
} as const;
export type NotificationEventType =
  (typeof NotificationEventType)[keyof typeof NotificationEventType];

export const NotificationDeliveryStatus = {
  SENT: "SENT",
  SKIPPED_NOT_CONFIGURED: "SKIPPED_NOT_CONFIGURED",
  FAILED: "FAILED",
} as const;
export type NotificationDeliveryStatus =
  (typeof NotificationDeliveryStatus)[keyof typeof NotificationDeliveryStatus];

/* ── Domain Models ──────────────────────────────────────────────────── */

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  department: string | null;
  manager_id: string | null;
}

export interface GoalCycle {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: CycleStatus;
}

export interface ThrustArea {
  id: string;
  name: string;
  description: string | null;
  cycle_id: string;
}

export interface Goal {
  id: string;
  employee_id: string;
  cycle_id: string;
  thrust_area_id: string | null;
  title: string;
  description: string | null;
  uom_type: UomType;
  target_value: string | null;
  target_date: string | null;
  weightage: number;
  version: number;
  status: GoalStatus;
  is_shared: boolean;
  shared_source_id: string | null;
  approved_at: string | null;
  locked_at: string | null;
  returned_reason: string | null;
}

export interface Achievement {
  id: string;
  goal_id: string;
  quarter: Quarter;
  planned_value: string | null;
  actual_value: string | null;
  completion_date: string | null;
  status: GoalProgress;
  computed_score: string | null;
}

export interface CheckinComment {
  id: string;
  goal_id: string;
  manager_id: string;
  quarter: Quarter;
  comment: string;
}

export interface CheckinWindow {
  id: string;
  cycle_id: string;
  quarter: Quarter;
  opens_at: string;
  closes_at: string;
}

export interface TeamCheckinRow {
  employee_id: string;
  employee_name: string;
  goal_id: string;
  goal_title: string;
  quarter: Quarter;
  planned_value: string | null;
  actual_value: string | null;
  achievement_status: GoalProgress | null;
  computed_score: string | null;
  manager_comment: string | null;
}

export interface EscalationRule {
  id: string;
  event_type: EscalationEventType;
  threshold_days: number;
  escalation_level: number;
  is_active: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface EscalationLog {
  id: string;
  cycle_id: string;
  target_user_id: string;
  manager_id: string | null;
  rule_id: string;
  event_type: EscalationEventType;
  status: EscalationStatus;
  detail: string | null;
  triggered_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
}

export interface AuditLog {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  changed_by: string;
  changed_by_name: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  reason: string | null;
  created_at: string;
}

export interface NotificationLog {
  id: string;
  cycle_id: string | null;
  goal_id: string | null;
  escalation_log_id: string | null;
  recipient_user_id: string | null;
  recipient_email: string | null;
  channel: NotificationChannel;
  event_type: NotificationEventType;
  status: NotificationDeliveryStatus;
  subject: string;
  detail: string | null;
  error_message: string | null;
  attempted_at: string;
}

export interface DistributionBucket {
  key: string;
  count: number;
}

export interface QoqAnalyticsResponse {
  cycle_id: string;
  rows: {
    quarter: Quarter;
    department: string | null;
    goal_count: number;
    achievement_count: number;
    average_score: number | null;
  }[];
}

export interface CompletionHeatmapResponse {
  cycle_id: string;
  rows: {
    quarter: Quarter;
    department: string | null;
    total_goals: number;
    achievement_updates: number;
    manager_comments: number;
  }[];
}

export interface DistributionResponse {
  cycle_id: string;
  goal_status: DistributionBucket[];
  progress_status: DistributionBucket[];
  thrust_area: DistributionBucket[];
  uom_type: DistributionBucket[];
}

export interface ManagerEffectivenessRow {
  manager_id: string;
  manager_name: string;
  department: string | null;
  team_members: number;
  total_goals: number;
  approved_goals: number;
  goals_returned: number;
  return_rate_percent: number;
  achievement_updates: number;
  manager_comments: number;
  average_score: number | null;
  checkin_coverage_percent: number;
  approval_turnaround_avg_days: number | null;
  overdue_checkins: number;
}

export interface ManagerEffectivenessResponse {
  cycle_id: string;
  rows: ManagerEffectivenessRow[];
}

export interface ManagerScorecardResponse extends ManagerEffectivenessRow {
  cycle_id: string;
  team_breakdown: {
    employee_id: string;
    employee_name: string;
    department: string | null;
    total_goals: number;
    approved_goals: number;
    average_score: number | null;
  }[];
}

export interface CompletionReportRow {
  id: string;
  name: string;
  manager_id: string | null;
  total_goals: number;
  achievement_updates: number;
  manager_comments: number;
}

/* ── API Request/Response shapes ────────────────────────────────────── */

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface GoalCreateRequest {
  cycle_id: string;
  thrust_area_id?: string | null;
  title: string;
  description?: string | null;
  uom_type: UomType;
  target_value?: string | null;
  target_date?: string | null;
  weightage: number;
}

export interface GoalUpdateRequest {
  thrust_area_id?: string | null;
  title?: string;
  description?: string | null;
  uom_type?: UomType;
  target_value?: string | null;
  target_date?: string | null;
  weightage?: number;
}

export interface ManagerGoalEditRequest {
  target_value?: string | null;
  target_date?: string | null;
  weightage?: number;
}

export interface SharedGoalCreateRequest extends GoalCreateRequest {
  employee_ids: string[];
}

export interface EscalationRuleCreateRequest {
  event_type: EscalationEventType;
  threshold_days: number;
  escalation_level: number;
  is_active: boolean;
  description?: string | null;
}

export interface EscalationRuleUpdateRequest {
  threshold_days?: number;
  escalation_level?: number;
  is_active?: boolean;
  description?: string | null;
}

export interface AchievementUpsert {
  quarter: Quarter;
  planned_value?: string | null;
  actual_value?: string | null;
  completion_date?: string | null;
  status?: GoalProgress;
}

export interface Message {
  message: string;
}

export interface SystemCapabilities {
  demo_mode: boolean;
  auth: {
    password: boolean;
    microsoft_sso: boolean;
  };
  notifications: {
    email: boolean;
    teams: boolean;
  };
  exports: {
    csv: boolean;
    xlsx: boolean;
  };
}
