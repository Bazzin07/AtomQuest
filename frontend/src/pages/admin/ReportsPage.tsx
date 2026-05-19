import { useQuery } from "@tanstack/react-query";
import { Download, FileSpreadsheet, FileText, MessageSquare, Target, TrendingUp, Users } from "lucide-react";
import { cycleApi, reportApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/spinner";
import type { CompletionReportRow, GoalCycle } from "@/types/api";

export default function ReportsPage() {
  const { data: cycles, isLoading } = useQuery({ queryKey: ["cycles"], queryFn: cycleApi.list });
  const activeCycle = cycles?.find((cycle: GoalCycle) => cycle.status === "ACTIVE");

  const { data: completion, isLoading: loadingCompletion } = useQuery({
    queryKey: ["completion", activeCycle?.id],
    queryFn: () => reportApi.completion(activeCycle!.id),
    enabled: !!activeCycle,
  });

  if (isLoading || loadingCompletion) return <PageLoader />;

  const handleExport = async (format: "csv" | "xlsx") => {
    if (!activeCycle) return;
    const blob = await reportApi.exportAchievement(activeCycle.id, format);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `achievement-report.${format}`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  if (!activeCycle) {
    return <EmptyState icon={<FileText className="h-12 w-12" />} title="No active cycle" description="Reports are generated for active cycles." />;
  }

  const rows = completion ?? [];
  const totalGoals = rows.reduce((sum: number, row: CompletionReportRow) => sum + row.total_goals, 0);
  const achievementUpdates = rows.reduce((sum: number, row: CompletionReportRow) => sum + row.achievement_updates, 0);
  const managerComments = rows.reduce((sum: number, row: CompletionReportRow) => sum + row.manager_comments, 0);
  const updateCoverage = totalGoals ? Math.round((achievementUpdates / totalGoals) * 100) : 0;

  return (
    <div className="space-y-5">
      <section className="app-panel rounded-lg p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="page-kicker">Reports</p>
            <h2 className="mt-2 text-2xl font-semibold">Achievement Exports</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Download CSV or Excel outputs and scan completion readiness for {activeCycle.name}.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => handleExport("csv")}>
              <Download className="h-4 w-4" />
              CSV
            </Button>
            <Button onClick={() => handleExport("xlsx")}>
              <FileSpreadsheet className="h-4 w-4" />
              XLSX
            </Button>
          </div>
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={Users} label="Employees" value={rows.length} />
        <Metric icon={Target} label="Goals" value={totalGoals} />
        <Metric icon={TrendingUp} label="Achievement updates" value={achievementUpdates} />
        <Metric icon={MessageSquare} label="Manager comments" value={managerComments} />
      </div>

      <Card className="app-panel">
        <CardContent className="p-0">
          <div className="flex flex-col justify-between gap-2 border-b border-[var(--border)] px-5 py-4 md:flex-row md:items-center">
            <div>
              <h3 className="font-semibold">Completion dashboard</h3>
              <p className="text-sm text-[var(--muted-foreground)]">{updateCoverage}% achievement update coverage across tracked goals.</p>
            </div>
          </div>

          {rows.length === 0 ? (
            <div className="p-8">
              <EmptyState icon={<FileText className="h-12 w-12" />} title="No report rows" description="Completion rows appear after employees create goals." />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--secondary)] text-xs text-[var(--muted-foreground)]">
                  <tr>
                    <th className="px-5 py-3 font-medium">Employee</th>
                    <th className="px-5 py-3 font-medium">Goals</th>
                    <th className="px-5 py-3 font-medium">Achievement updates</th>
                    <th className="px-5 py-3 font-medium">Manager comments</th>
                    <th className="px-5 py-3 font-medium">Coverage</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] bg-white">
                  {rows.map((row: CompletionReportRow) => {
                    const coverage = row.total_goals ? Math.round((row.achievement_updates / row.total_goals) * 100) : 0;
                    return (
                      <tr key={row.id}>
                        <td className="px-5 py-4">
                          <p className="font-medium">{row.name}</p>
                          <p className="text-xs text-[var(--muted-foreground)]">{row.id.slice(0, 8)}</p>
                        </td>
                        <td className="px-5 py-4 font-mono text-xs">{row.total_goals}</td>
                        <td className="px-5 py-4 font-mono text-xs">{row.achievement_updates}</td>
                        <td className="px-5 py-4 font-mono text-xs">{row.manager_comments}</td>
                        <td className="px-5 py-4">
                          <div className="flex min-w-32 items-center gap-2">
                            <div className="h-2 flex-1 rounded-full bg-[var(--secondary)]">
                              <div className="h-2 rounded-full bg-[var(--primary)]" style={{ width: `${Math.min(coverage, 100)}%` }} />
                            </div>
                            <span className="w-10 text-right font-mono text-xs">{coverage}%</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: number }) {
  return (
    <Card className="app-panel">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="metric-label">{label}</p>
            <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--secondary)] text-[var(--primary)]">
            <Icon className="h-4.5 w-4.5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
