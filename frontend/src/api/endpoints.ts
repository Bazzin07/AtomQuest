import api from "./client";
import type {
  Achievement,
  AchievementUpsert,
  CheckinComment,
  CheckinWindow,
  AuditLog,
  NotificationLog,
  EscalationLog,
  EscalationRule,
  EscalationRuleCreateRequest,
  EscalationRuleUpdateRequest,
  Goal,
  GoalCreateRequest,
  GoalCycle,
  GoalUpdateRequest,
  LoginRequest,
  ManagerGoalEditRequest,
  Message,
  SharedGoalCreateRequest,
  ThrustArea,
  TokenResponse,
  User,
  CompletionHeatmapResponse,
  DistributionResponse,
  ManagerEffectivenessResponse,
  ManagerScorecardResponse,
  QoqAnalyticsResponse,
  CompletionReportRow,
  TeamCheckinRow,
  SystemCapabilities,
} from "@/types/api";

/* ── Auth ────────────────────────────────────────────────────────────── */
export const authApi = {
  login: (data: LoginRequest) =>
    api.post<TokenResponse>("/auth/login", data).then((r) => r.data),
  me: () => api.get<User>("/auth/me").then((r) => r.data),
  refresh: () => api.post<TokenResponse>("/auth/refresh").then((r) => r.data),
  logout: () => api.post("/auth/logout"),
  microsoftStart: () =>
    api.get<{ authorization_url: string }>("/auth/microsoft/start").then((r) => r.data),
};

export const systemApi = {
  capabilities: () =>
    api.get<SystemCapabilities>("/system/capabilities").then((r) => r.data),
};

/* ── Cycles ──────────────────────────────────────────────────────────── */
export const cycleApi = {
  list: () => api.get<GoalCycle[]>("/admin/cycles").then((r) => r.data),
  create: (data: { name: string; start_date: string; end_date: string }) =>
    api.post<GoalCycle>("/admin/cycles", data).then((r) => r.data),
};

/* ── Thrust Areas ────────────────────────────────────────────────────── */
export const thrustAreaApi = {
  list: (cycleId: string) =>
    api
      .get<ThrustArea[]>("/admin/thrust-areas", {
        params: { cycle_id: cycleId },
      })
      .then((r) => r.data),
  create: (data: {
    name: string;
    description?: string;
    cycle_id: string;
  }) =>
    api.post<ThrustArea>("/admin/thrust-areas", data).then((r) => r.data),
};

/* ── Goals ───────────────────────────────────────────────────────────── */
export const goalApi = {
  listMy: (cycleId: string) =>
    api
      .get<Goal[]>("/goals", { params: { cycle_id: cycleId } })
      .then((r) => r.data),
  listTeam: (cycleId: string) =>
    api
      .get<Goal[]>("/goals/team", { params: { cycle_id: cycleId } })
      .then((r) => r.data),
  get: (id: string) => api.get<Goal>(`/goals/${id}`).then((r) => r.data),
  create: (data: GoalCreateRequest) =>
    api.post<Goal>("/goals", data).then((r) => r.data),
  update: (id: string, data: GoalUpdateRequest, version: number) =>
    api
      .patch<Goal>(`/goals/${id}`, data, {
        headers: { "If-Match": String(version) },
      })
      .then((r) => r.data),
  delete: (id: string) => api.delete(`/goals/${id}`),
  submit: (cycleId: string) =>
    api
      .post<Message>("/goals/submit", { cycle_id: cycleId })
      .then((r) => r.data),
  approve: (goalId: string) =>
    api.post<Message>(`/goals/${goalId}/approve`).then((r) => r.data),
  returnGoal: (goalId: string, reason: string) =>
    api
      .post<Message>(`/goals/${goalId}/return`, { reason })
      .then((r) => r.data),
  lock: (goalId: string) =>
    api.post<Message>(`/goals/${goalId}/lock`).then((r) => r.data),
  managerEdit: (goalId: string, data: ManagerGoalEditRequest) =>
    api.put<Goal>(`/goals/${goalId}/manager-edit`, data).then((r) => r.data),
  createShared: (data: SharedGoalCreateRequest) =>
    api.post<Goal[]>("/goals/shared", data).then((r) => r.data),
};

/* ── Users ───────────────────────────────────────────────────────────── */
export const userApi = {
  team: () => api.get<User[]>("/users/team").then((r) => r.data),
};

/* ── Achievements ────────────────────────────────────────────────────── */
export const achievementApi = {
  list: (goalId: string) =>
    api
      .get<Achievement[]>("/achievements", { params: { goal_id: goalId } })
      .then((r) => r.data),
  upsert: (goalId: string, data: AchievementUpsert) =>
    api
      .put<Achievement>(`/achievements/${goalId}`, data)
      .then((r) => r.data),
};

/* ── Check-ins ───────────────────────────────────────────────────────── */
export const checkinApi = {
  windows: (cycleId: string) =>
    api
      .get<CheckinWindow[]>("/admin/checkin-windows", {
        params: { cycle_id: cycleId },
      })
      .then((r) => r.data),
  teamCheckins: (cycleId: string, quarter: string) =>
    api
      .get<TeamCheckinRow[]>("/checkins/team", {
        params: { cycle_id: cycleId, quarter },
      })
      .then((r) => r.data),
  addComment: (goalId: string, data: { quarter: string; comment: string }) =>
    api
      .post<CheckinComment>(`/checkins/${goalId}`, data)
      .then((r) => r.data),
};

/* ── Escalations ─────────────────────────────────────────────────────── */
export const escalationApi = {
  listRules: () =>
    api.get<EscalationRule[]>("/escalations/rules").then((r) => r.data),
  createRule: (
    data: EscalationRuleCreateRequest,
  ) =>
    api.post<EscalationRule>("/escalations/rules", data).then((r) => r.data),
  updateRule: (ruleId: string, data: EscalationRuleUpdateRequest) =>
    api.patch<EscalationRule>(`/escalations/rules/${ruleId}`, data).then((r) => r.data),
  evaluate: (cycleId: string) =>
    api
      .post("/escalations/evaluate", null, {
        params: { cycle_id: cycleId },
      })
      .then((r) => r.data),
  listLogs: (cycleId: string) =>
    api
      .get<EscalationLog[]>("/escalations/logs", {
        params: { cycle_id: cycleId },
      })
      .then((r) => r.data),
  resolve: (logId: string) =>
    api
      .patch<EscalationLog>(`/escalations/logs/${logId}/resolve`)
      .then((r) => r.data),
};

/* ── Analytics ───────────────────────────────────────────────────────── */
export const analyticsApi = {
  qoq: (cycleId: string) =>
    api
      .get<QoqAnalyticsResponse>("/analytics/qoq", { params: { cycle_id: cycleId } })
      .then((r) => r.data),
  managerEffectiveness: (cycleId: string) =>
    api
      .get<ManagerEffectivenessResponse>("/analytics/manager-effectiveness", {
        params: { cycle_id: cycleId },
      })
      .then((r) => r.data),
  distribution: (cycleId: string) =>
    api
      .get<DistributionResponse>("/analytics/distribution", { params: { cycle_id: cycleId } })
      .then((r) => r.data),
  heatmap: (cycleId: string) =>
    api
      .get<CompletionHeatmapResponse>("/analytics/completion-heatmap", { params: { cycle_id: cycleId } })
      .then((r) => r.data),
  scorecard: (managerId: string, cycleId: string) =>
    api
      .get<ManagerScorecardResponse>(`/analytics/manager-scorecard/${managerId}`, {
        params: { cycle_id: cycleId },
      })
      .then((r) => r.data),
};

/* ── Reports ─────────────────────────────────────────────────────────── */
export const reportApi = {
  completion: (cycleId: string) =>
    api
      .get<CompletionReportRow[]>("/reports/completion", { params: { cycle_id: cycleId } })
      .then((r) => r.data),
  exportAchievement: (cycleId: string, format: "csv" | "xlsx") =>
    api
      .get("/reports/achievement", {
        params: { cycle_id: cycleId, format },
        responseType: "blob",
      })
      .then((r) => r.data),
};

/* ── Admin ───────────────────────────────────────────────────────────── */
export const adminApi = {
  unlockGoal: (goalId: string) =>
    api.post<Message>(`/admin/goals/${goalId}/unlock`).then((r) => r.data),
  createCheckinWindow: (data: {
    cycle_id: string;
    quarter: string;
    opens_at: string;
    closes_at: string;
  }) =>
    api
      .post<CheckinWindow>("/admin/checkin-windows", data)
      .then((r) => r.data),
  updateCheckinWindow: (
    windowId: string,
    data: { opens_at?: string; closes_at?: string },
  ) =>
    api.patch<CheckinWindow>(`/admin/checkin-windows/${windowId}`, data).then((r) => r.data),
  notifications: (params?: {
    channel?: string;
    event_type?: string;
    status_filter?: string;
    page?: number;
    size?: number;
  }) =>
    api
      .get<NotificationLog[]>("/admin/notifications", { params })
      .then((r) => r.data),
};

export const auditApi = {
  list: (params?: { entity_type?: string; page?: number; size?: number }) =>
    api
      .get<AuditLog[]>("/audit", {
        params,
      })
      .then((r) => r.data),
};
