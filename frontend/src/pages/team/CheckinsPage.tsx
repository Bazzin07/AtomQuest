import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCheck, MessageSquare, Send, X } from "lucide-react";
import { checkinApi, cycleApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/spinner";
import { GoalProgress, type GoalCycle, type Quarter, type TeamCheckinRow } from "@/types/api";

const QUARTERS: Quarter[] = ["Q1", "Q2", "Q3", "Q4"];

const PROGRESS_TONE: Record<GoalProgress, string> = {
  NOT_STARTED: "bg-zinc-100 text-zinc-700",
  ON_TRACK: "bg-amber-50 text-amber-700",
  COMPLETED: "bg-emerald-50 text-emerald-700",
};

function progressLabel(status: GoalProgress | null) {
  return status ? status.replace(/_/g, " ") : "No update";
}

export default function CheckinsPage() {
  const queryClient = useQueryClient();
  const [selectedQuarter, setSelectedQuarter] = useState<Quarter>("Q1");
  const [commentGoalId, setCommentGoalId] = useState<string | null>(null);
  const [commentText, setCommentText] = useState("");

  const { data: cycles, isLoading: loadingCycles } = useQuery({ queryKey: ["cycles"], queryFn: cycleApi.list });
  const activeCycle = cycles?.find((cycle: GoalCycle) => cycle.status === "ACTIVE");

  const { data: rows, isLoading: loadingRows } = useQuery({
    queryKey: ["teamCheckins", activeCycle?.id, selectedQuarter],
    queryFn: () => checkinApi.teamCheckins(activeCycle!.id, selectedQuarter),
    enabled: !!activeCycle,
  });

  const commentMutation = useMutation({
    mutationFn: ({ goalId, quarter, comment }: { goalId: string; quarter: Quarter; comment: string }) =>
      checkinApi.addComment(goalId, { quarter, comment }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teamCheckins"] });
      setCommentGoalId(null);
      setCommentText("");
    },
  });

  if (loadingCycles || loadingRows) return <PageLoader />;

  if (!activeCycle) {
    return (
      <EmptyState
        icon={<ClipboardCheck className="h-12 w-12" />}
        title="No active cycle"
        description="Check-ins are available during active cycles."
      />
    );
  }

  const checkins = rows ?? [];
  const withAchievements = checkins.filter((row: TeamCheckinRow) => row.actual_value !== null).length;
  const withComments = checkins.filter((row: TeamCheckinRow) => row.manager_comment).length;

  return (
    <div className="space-y-5">
      <section className="app-panel rounded-lg p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="page-kicker">Quarterly check-ins</p>
            <h2 className="mt-2 text-2xl font-semibold">{activeCycle.name}</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Review actuals, computed scores, and manager comments for each locked team goal.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-sm">
            <Metric value={checkins.length} label="Goals" />
            <Metric value={withAchievements} label="Actuals" />
            <Metric value={withComments} label="Comments" />
          </div>
        </div>
      </section>

      <Card className="app-panel">
        <CardContent className="p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-5 py-4">
            <div className="flex gap-1 rounded-lg bg-[var(--secondary)] p-1">
              {QUARTERS.map((quarter) => (
                <button
                  key={quarter}
                  onClick={() => setSelectedQuarter(quarter)}
                  className={`h-9 rounded-md px-4 text-sm font-medium transition-colors ${
                    selectedQuarter === quarter ? "bg-white text-[var(--foreground)] shadow-sm" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {quarter}
                </button>
              ))}
            </div>
            <div className="text-sm text-[var(--muted-foreground)]">{selectedQuarter} review window</div>
          </div>

          {checkins.length === 0 ? (
            <div className="p-8">
              <EmptyState
                icon={<ClipboardCheck className="h-12 w-12" />}
                title="No check-in rows"
                description="Approved or locked team goals will appear here for quarterly review."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--secondary)] text-xs text-[var(--muted-foreground)]">
                  <tr>
                    <th className="px-5 py-3 font-medium">Employee</th>
                    <th className="px-5 py-3 font-medium">Goal</th>
                    <th className="px-5 py-3 font-medium">Planned</th>
                    <th className="px-5 py-3 font-medium">Actual</th>
                    <th className="px-5 py-3 font-medium">Score</th>
                    <th className="px-5 py-3 font-medium">Progress</th>
                    <th className="px-5 py-3 text-right font-medium">Comment</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] bg-white">
                  {checkins.map((row: TeamCheckinRow) => (
                    <tr key={`${row.goal_id}-${row.quarter}`} className="align-top">
                      <td className="px-5 py-4">
                        <p className="font-medium">{row.employee_name}</p>
                        <p className="text-xs text-[var(--muted-foreground)]">{row.employee_id.slice(0, 8)}</p>
                      </td>
                      <td className="max-w-sm px-5 py-4">
                        <p className="line-clamp-2 font-medium">{row.goal_title}</p>
                        {row.manager_comment && <p className="mt-2 rounded-md bg-[var(--secondary)] px-2 py-1 text-xs text-[var(--muted-foreground)]">{row.manager_comment}</p>}
                      </td>
                      <td className="px-5 py-4 font-mono text-xs">{row.planned_value ?? "N/A"}</td>
                      <td className="px-5 py-4 font-mono text-xs">{row.actual_value ?? "N/A"}</td>
                      <td className="px-5 py-4 font-mono text-xs">{row.computed_score ?? "N/A"}</td>
                      <td className="px-5 py-4">
                        <span className={`rounded-md px-2 py-1 text-xs ${row.achievement_status ? PROGRESS_TONE[row.achievement_status] : "bg-zinc-100 text-zinc-600"}`}>
                          {progressLabel(row.achievement_status)}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-right">
                        {commentGoalId === row.goal_id ? (
                          <div className="ml-auto flex max-w-md items-start gap-2">
                            <textarea
                              value={commentText}
                              onChange={(event) => setCommentText(event.target.value)}
                              className="min-h-20 w-64 rounded-lg border border-[var(--input)] px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                              placeholder={`${selectedQuarter} check-in comment`}
                              autoFocus
                            />
                            <div className="flex flex-col gap-1">
                              <Button
                                size="icon"
                                className="h-9 w-9"
                                onClick={() => commentMutation.mutate({ goalId: row.goal_id, quarter: selectedQuarter, comment: commentText })}
                                disabled={commentText.length < 3 || commentMutation.isPending}
                                aria-label="Save comment"
                              >
                                <Send className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-9 w-9"
                                onClick={() => {
                                  setCommentGoalId(null);
                                  setCommentText("");
                                }}
                                aria-label="Cancel comment"
                              >
                                <X className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setCommentGoalId(row.goal_id);
                              setCommentText(row.manager_comment ?? "");
                            }}
                          >
                            <MessageSquare className="h-3.5 w-3.5" />
                            {row.manager_comment ? "Edit" : "Comment"}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-lg bg-white px-4 py-3">
      <p className="font-semibold tabular-nums">{value}</p>
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
    </div>
  );
}
