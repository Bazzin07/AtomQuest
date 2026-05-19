import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, CheckCircle2, Clock, Lock, Target, TrendingUp, Users } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { checkinApi, cycleApi, goalApi, reportApi } from "@/api/endpoints";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/spinner";
import { useAuthStore } from "@/stores/auth";
import { GoalStatus, type CheckinWindow, type Goal, type GoalCycle } from "@/types/api";

const STAGGER = {
  container: { transition: { staggerChildren: 0.05 } },
  item: {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.24 },
  },
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function formatWindow(window: CheckinWindow) {
  return `${window.quarter} ${new Intl.DateTimeFormat("en", { month: "short" }).format(new Date(window.opens_at))}`;
}

function StatTile({
  label,
  value,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  icon: React.ElementType;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  const toneClass = {
    default: "bg-[var(--secondary)] text-[var(--primary)]",
    success: "bg-emerald-50 text-emerald-700",
    warning: "bg-amber-50 text-amber-700",
    danger: "bg-rose-50 text-rose-700",
  }[tone];

  return (
    <motion.div variants={STAGGER.item}>
      <Card className="app-panel">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="metric-label">{label}</p>
              <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
            </div>
            <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${toneClass}`}>
              <Icon className="h-4.5 w-4.5" />
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)!;
  const { data: cycles, isLoading } = useQuery({ queryKey: ["cycles"], queryFn: cycleApi.list });
  const activeCycle = cycles?.find((cycle: GoalCycle) => cycle.status === "ACTIVE");
  const { data: windows } = useQuery({
    queryKey: ["checkinWindows", activeCycle?.id],
    queryFn: () => checkinApi.windows(activeCycle!.id),
    enabled: !!activeCycle,
  });

  if (isLoading) return <PageLoader />;
  if (!activeCycle) {
    return (
      <EmptyState
        icon={<Clock className="h-12 w-12" />}
        title="No active cycle"
        description="There is no active goal cycle. Contact your administrator to create one."
      />
    );
  }

  return (
    <motion.div variants={STAGGER.container} initial="initial" animate="animate" className="space-y-6">
      <motion.section variants={STAGGER.item} className="app-panel rounded-lg p-5">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="page-kicker">Active cycle</p>
            <h2 className="mt-2 text-3xl font-semibold">Welcome back, {user.name.split(" ")[0]}</h2>
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">
              {activeCycle.name} runs from {formatDate(activeCycle.start_date)} to {formatDate(activeCycle.end_date)}.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            {(windows ?? []).length === 0 ? (
              <div className="col-span-2 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-center sm:col-span-4">
                No check-in windows configured
              </div>
            ) : (
              (windows ?? []).map((window) => (
                <div key={window.id} className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-center">
                  <p className="font-medium">{formatWindow(window)}</p>
                  <p className="mt-1 text-[10px] text-[var(--muted-foreground)]">
                    {formatDate(window.opens_at)} to {formatDate(window.closes_at)}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </motion.section>

      {user.role === "EMPLOYEE" ? (
        <EmployeeDashboard cycleId={activeCycle.id} />
      ) : user.role === "MANAGER" ? (
        <ManagerDashboard cycleId={activeCycle.id} />
      ) : (
        <AdminDashboard cycleId={activeCycle.id} />
      )}
    </motion.div>
  );
}

function EmployeeDashboard({ cycleId }: { cycleId: string }) {
  const navigate = useNavigate();
  const { data: goals, isLoading } = useQuery({
    queryKey: ["goals", cycleId],
    queryFn: () => goalApi.listMy(cycleId),
  });

  if (isLoading) return <PageLoader />;

  const goalList = goals ?? [];
  const totalWeightage = goalList.reduce((sum: number, goal: Goal) => sum + goal.weightage, 0);
  const submitted = goalList.filter((goal: Goal) => goal.status === GoalStatus.SUBMITTED).length;
  const locked = goalList.filter((goal: Goal) => goal.status === GoalStatus.LOCKED).length;
  const needsWork = goalList.filter((goal: Goal) => goal.status === GoalStatus.DRAFT || goal.status === GoalStatus.RETURNED).length;

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Goals" value={`${goalList.length}/8`} icon={Target} />
        <StatTile label="Weightage" value={`${totalWeightage}%`} icon={TrendingUp} tone={totalWeightage === 100 ? "success" : "warning"} />
        <StatTile label="Awaiting review" value={submitted} icon={Clock} tone={submitted ? "warning" : "default"} />
        <StatTile label="Locked" value={locked} icon={Lock} tone="success" />
      </div>

      <Card className="app-panel">
        <CardContent className="p-0">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
            <div>
              <h3 className="text-base font-semibold">Goal sheet</h3>
              <p className="text-sm text-[var(--muted-foreground)]">{needsWork} item(s) still editable before submission.</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => navigate("/goals")}>
              Open sheet
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
          {goalList.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={<Target className="h-10 w-10" />}
                title="No goals yet"
                description="Create up to 8 weighted goals for the active cycle."
                action={<Button onClick={() => navigate("/goals")}>Create Goal</Button>}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--secondary)] text-xs text-[var(--muted-foreground)]">
                  <tr>
                    <th className="px-5 py-3 font-medium">Goal</th>
                    <th className="px-5 py-3 font-medium">Measure</th>
                    <th className="px-5 py-3 font-medium">Weight</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {goalList.slice(0, 6).map((goal: Goal) => (
                    <tr key={goal.id} className="bg-white">
                      <td className="max-w-sm px-5 py-3">
                        <p className="truncate font-medium">{goal.title}</p>
                        <p className="truncate text-xs text-[var(--muted-foreground)]">{goal.description ?? "No description"}</p>
                      </td>
                      <td className="px-5 py-3 font-mono text-xs">{goal.uom_type.replace(/_/g, " ")}</td>
                      <td className="px-5 py-3 font-mono text-xs">{goal.weightage}%</td>
                      <td className="px-5 py-3"><StatusBadge status={goal.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function ManagerDashboard({ cycleId }: { cycleId: string }) {
  const navigate = useNavigate();
  const { data: teamGoals, isLoading } = useQuery({
    queryKey: ["teamGoals", cycleId],
    queryFn: () => goalApi.listTeam(cycleId),
  });

  if (isLoading) return <PageLoader />;

  const goals = teamGoals ?? [];
  const pendingReview = goals.filter((goal: Goal) => goal.status === GoalStatus.SUBMITTED);
  const approved = goals.filter((goal: Goal) => goal.status === GoalStatus.APPROVED);
  const returned = goals.filter((goal: Goal) => goal.status === GoalStatus.RETURNED);
  const locked = goals.filter((goal: Goal) => goal.status === GoalStatus.LOCKED);

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Team goals" value={goals.length} icon={Users} />
        <StatTile label="Pending review" value={pendingReview.length} icon={Clock} tone={pendingReview.length ? "warning" : "default"} />
        <StatTile label="Approved" value={approved.length} icon={CheckCircle2} tone="success" />
        <StatTile label="Returned" value={returned.length} icon={AlertTriangle} tone={returned.length ? "danger" : "default"} />
      </div>

      <Card className="app-panel">
        <CardContent className="p-0">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
            <div>
              <h3 className="text-base font-semibold">Manager review queue</h3>
              <p className="text-sm text-[var(--muted-foreground)]">{locked.length} locked goals are ready for quarterly tracking.</p>
            </div>
            <Button size="sm" onClick={() => navigate("/team")}>
              Review queue
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
          {goals.length === 0 ? (
            <div className="p-6">
              <EmptyState icon={<Users className="h-10 w-10" />} title="No team goals" description="Submitted team goals will appear here." />
            </div>
          ) : (
            <div className="divide-y divide-[var(--border)]">
              {goals.slice(0, 7).map((goal: Goal) => (
                <div key={goal.id} className="flex items-center justify-between gap-4 px-5 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{goal.title}</p>
                    <p className="text-xs text-[var(--muted-foreground)]">{goal.weightage}% / {goal.uom_type.replace(/_/g, " ")}</p>
                  </div>
                  <StatusBadge status={goal.status} />
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function AdminDashboard({ cycleId }: { cycleId: string }) {
  const navigate = useNavigate();
  const { data: cycles } = useQuery({ queryKey: ["cycles"], queryFn: cycleApi.list });
  const activeCycle = cycles?.find((cycle: GoalCycle) => cycle.id === cycleId);
  const { data: report } = useQuery({
    queryKey: ["completion", cycleId],
    queryFn: () => reportApi.completion(cycleId),
  });

  const rows = Array.isArray(report) ? report : [];
  const totalGoals = rows.reduce((sum, row: { total_goals?: number }) => sum + (row.total_goals ?? 0), 0);
  const achievementUpdates = rows.reduce((sum, row: { achievement_updates?: number }) => sum + (row.achievement_updates ?? 0), 0);
  const managerComments = rows.reduce((sum, row: { manager_comments?: number }) => sum + (row.manager_comments ?? 0), 0);

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Cycle status" value={activeCycle?.status ?? "ACTIVE"} icon={CheckCircle2} tone="success" />
        <StatTile label="Employees with goals" value={rows.length} icon={Users} />
        <StatTile label="Goals tracked" value={totalGoals} icon={Target} />
        <StatTile label="Achievement updates" value={achievementUpdates} icon={TrendingUp} tone={achievementUpdates ? "success" : "default"} />
      </div>

      <Card className="app-panel">
        <CardContent className="p-5">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <p className="page-kicker">Admin command center</p>
              <h3 className="mt-2 text-lg font-semibold">Operational readiness</h3>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                {managerComments} manager comments captured across the active cycle.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => navigate("/admin/cycles")}>Cycles</Button>
              <Button variant="outline" onClick={() => navigate("/admin/escalations")}>Escalations</Button>
              <Button variant="outline" onClick={() => navigate("/admin/notifications")}>Notifications</Button>
              <Button variant="outline" onClick={() => navigate("/analytics")}>Analytics</Button>
              <Button variant="outline" onClick={() => navigate("/admin/reports")}>Reports</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
