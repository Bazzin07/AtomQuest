import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { BarChart3, Clock, Target, Users } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { analyticsApi, cycleApi } from "@/api/endpoints";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/spinner";
import { useAuthStore } from "@/stores/auth";
import type { GoalCycle } from "@/types/api";

const COLORS = ["#0f766e", "#2563eb", "#b7791f", "#dc2626", "#64748b", "#15803d"];

const STAGGER = {
  container: { transition: { staggerChildren: 0.06 } },
  item: {
    initial: { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.26 },
  },
};

export default function AnalyticsPage() {
  const user = useAuthStore((state) => state.user)!;
  const { data: cycles, isLoading: loadingCycles } = useQuery({ queryKey: ["cycles"], queryFn: cycleApi.list });
  const activeCycle = cycles?.find((cycle: GoalCycle) => cycle.status === "ACTIVE");

  const { data: distribution, isLoading: loadingDistribution } = useQuery({
    queryKey: ["distribution", activeCycle?.id],
    queryFn: () => analyticsApi.distribution(activeCycle!.id),
    enabled: !!activeCycle,
  });

  const { data: heatmap, isLoading: loadingHeatmap } = useQuery({
    queryKey: ["heatmap", activeCycle?.id],
    queryFn: () => analyticsApi.heatmap(activeCycle!.id),
    enabled: !!activeCycle,
  });

  const { data: qoq, isLoading: loadingQoq } = useQuery({
    queryKey: ["qoq", activeCycle?.id],
    queryFn: () => analyticsApi.qoq(activeCycle!.id),
    enabled: !!activeCycle,
  });

  const { data: effectiveness, isLoading: loadingEffectiveness } = useQuery({
    queryKey: ["managerEffectiveness", activeCycle?.id],
    queryFn: () => analyticsApi.managerEffectiveness(activeCycle!.id),
    enabled: !!activeCycle,
  });

  const { data: scorecard } = useQuery({
    queryKey: ["scorecard", user.id, activeCycle?.id],
    queryFn: () => analyticsApi.scorecard(user.id, activeCycle!.id),
    enabled: !!activeCycle && user.role === "MANAGER",
  });

  if (loadingCycles) return <PageLoader />;
  if (!activeCycle) {
    return <EmptyState icon={<BarChart3 className="h-12 w-12" />} title="No active cycle" description="Analytics are available when a cycle is active." />;
  }

  if (loadingDistribution || loadingHeatmap || loadingQoq || loadingEffectiveness) return <PageLoader />;

  const statusData = distribution?.goal_status ?? [];
  const heatData =
    heatmap?.rows.map((row) => ({
      name: `${row.quarter} / ${row.department ?? "Unassigned"}`,
      updates: row.achievement_updates,
      comments: row.manager_comments,
      total: row.total_goals,
    })) ?? [];
  const qoqData =
    qoq?.rows.map((row) => ({
      name: `${row.quarter} / ${row.department ?? "Team"}`,
      score: row.average_score ?? 0,
      goals: row.goal_count,
    })) ?? [];
  const managerRows = effectiveness?.rows ?? [];

  return (
    <motion.div variants={STAGGER.container} initial="initial" animate="animate" className="space-y-5">
      <motion.section variants={STAGGER.item} className="app-panel rounded-lg p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="page-kicker">Analytics module</p>
            <h2 className="mt-2 text-2xl font-semibold">Performance intelligence</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Completion, distribution, quarter trends, and manager effectiveness across the active cycle.
            </p>
          </div>
          {scorecard && (
            <div className="grid grid-cols-3 gap-2 text-center text-sm">
              <Metric label="Team" value={scorecard.team_members} icon={Users} />
              <Metric label="Coverage" value={`${scorecard.checkin_coverage_percent}%`} icon={Target} />
              <Metric label="Overdue" value={scorecard.overdue_checkins} icon={Clock} />
            </div>
          )}
        </div>
      </motion.section>

      <div className="grid gap-5 xl:grid-cols-2">
        <motion.div variants={STAGGER.item}>
          <ChartPanel title="Goal Status Distribution" description="Current goal workflow state by count.">
            {statusData.length === 0 ? (
              <NoChartData />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie data={statusData} dataKey="count" nameKey="key" innerRadius={68} outerRadius={105} paddingAngle={3}>
                    {statusData.map((_, index) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartPanel>
        </motion.div>

        <motion.div variants={STAGGER.item}>
          <ChartPanel title="Check-in Completion" description="Achievement updates and manager comments by quarter.">
            {heatData.length === 0 ? (
              <NoChartData />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={heatData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="updates" fill="#0f766e" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="comments" fill="#2563eb" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartPanel>
        </motion.div>

        <motion.div variants={STAGGER.item}>
          <ChartPanel title="Quarter Score Trend" description="Average computed score by quarter and department.">
            {qoqData.length === 0 ? (
              <NoChartData />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={qoqData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Bar dataKey="score" fill="#0f766e" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartPanel>
        </motion.div>

        <motion.div variants={STAGGER.item}>
          <ChartPanel title="Manager Effectiveness" description="Review throughput, check-in coverage, and overdue signals.">
            {managerRows.length === 0 ? (
              <NoChartData />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-[var(--muted-foreground)]">
                    <tr>
                      <th className="pb-3 font-medium">Manager</th>
                      <th className="pb-3 font-medium">Goals</th>
                      <th className="pb-3 font-medium">Coverage</th>
                      <th className="pb-3 font-medium">Avg Score</th>
                      <th className="pb-3 font-medium">Overdue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {managerRows.map((row) => (
                      <tr key={row.manager_id}>
                        <td className="py-3">
                          <p className="font-medium">{row.manager_name}</p>
                          <p className="text-xs text-[var(--muted-foreground)]">{row.department ?? "Unassigned"}</p>
                        </td>
                        <td className="py-3 font-mono text-xs">{row.total_goals}</td>
                        <td className="py-3 font-mono text-xs">{row.checkin_coverage_percent}%</td>
                        <td className="py-3 font-mono text-xs">{row.average_score?.toFixed(1) ?? "N/A"}</td>
                        <td className="py-3 font-mono text-xs">{row.overdue_checkins}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </ChartPanel>
        </motion.div>
      </div>

      {scorecard && (
        <motion.div variants={STAGGER.item}>
          <ChartPanel title="Manager Scorecard" description="Current team breakdown for the signed-in manager.">
            <div className="grid gap-3 md:grid-cols-4">
              <Metric label="Approved" value={scorecard.approved_goals} icon={Target} />
              <Metric label="Returned" value={scorecard.goals_returned} icon={Clock} />
              <Metric label="Comments" value={scorecard.manager_comments} icon={Users} />
              <Metric label="Avg score" value={scorecard.average_score?.toFixed(1) ?? "N/A"} icon={BarChart3} />
            </div>
            <div className="mt-5 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs text-[var(--muted-foreground)]">
                  <tr>
                    <th className="pb-3 font-medium">Employee</th>
                    <th className="pb-3 font-medium">Department</th>
                    <th className="pb-3 font-medium">Goals</th>
                    <th className="pb-3 font-medium">Approved</th>
                    <th className="pb-3 font-medium">Avg Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {scorecard.team_breakdown.map((row) => (
                    <tr key={row.employee_id}>
                      <td className="py-3 font-medium">{row.employee_name}</td>
                      <td className="py-3 text-[var(--muted-foreground)]">{row.department ?? "Unassigned"}</td>
                      <td className="py-3 font-mono text-xs">{row.total_goals}</td>
                      <td className="py-3 font-mono text-xs">{row.approved_goals}</td>
                      <td className="py-3 font-mono text-xs">{row.average_score?.toFixed(1) ?? "N/A"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ChartPanel>
        </motion.div>
      )}
    </motion.div>
  );
}

function Metric({ label, value, icon: Icon }: { label: string; value: React.ReactNode; icon: React.ElementType }) {
  return (
    <div className="rounded-lg bg-white px-4 py-3">
      <Icon className="mx-auto mb-1 h-4 w-4 text-[var(--primary)]" />
      <p className="font-semibold tabular-nums">{value}</p>
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
    </div>
  );
}

function ChartPanel({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <Card className="app-panel h-full">
      <CardContent className="p-5">
        <div className="mb-5">
          <h3 className="text-base font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">{description}</p>
        </div>
        {children}
      </CardContent>
    </Card>
  );
}

function NoChartData() {
  return (
    <div className="flex h-[300px] items-center justify-center rounded-lg bg-[var(--secondary)] text-sm text-[var(--muted-foreground)]">
      No data available yet
    </div>
  );
}
