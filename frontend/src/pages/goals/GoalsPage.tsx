import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Activity, AlertCircle, CheckCircle2, Pencil, Plus, Send, Target, Trash2, X } from "lucide-react";
import { achievementApi, cycleApi, goalApi, thrustAreaApi } from "@/api/endpoints";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState, PageLoader } from "@/components/ui/spinner";
import {
  GoalProgress,
  GoalStatus,
  type Achievement,
  type Goal,
  type GoalCycle,
  type Quarter,
  type UomType,
} from "@/types/api";

const UOM_OPTIONS: { value: UomType; label: string }[] = [
  { value: "NUMERIC_MAX", label: "Numeric / higher is better" },
  { value: "NUMERIC_MIN", label: "Numeric / lower is better" },
  { value: "PERCENTAGE_MAX", label: "Percentage / higher" },
  { value: "PERCENTAGE_MIN", label: "Percentage / lower" },
  { value: "TIMELINE", label: "Timeline / deadline" },
  { value: "ZERO", label: "Zero target" },
];

const QUARTERS: Quarter[] = ["Q1", "Q2", "Q3", "Q4"];

const PROGRESS_OPTIONS: { value: GoalProgress; label: string }[] = [
  { value: "NOT_STARTED", label: "Not Started" },
  { value: "ON_TRACK", label: "On Track" },
  { value: "COMPLETED", label: "Completed" },
];

function GoalProgressRail({ totalWeightage, count }: { totalWeightage: number; count: number }) {
  const weightPercent = Math.min(totalWeightage, 100);
  const countPercent = Math.min((count / 8) * 100, 100);

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="rounded-lg border border-[var(--border)] bg-white p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">Weightage</span>
          <span className={totalWeightage === 100 ? "text-emerald-700" : "text-amber-700"}>{totalWeightage}% / 100%</span>
        </div>
        <div className="mt-3 h-2 rounded-full bg-[var(--secondary)]">
          <div className="h-2 rounded-full bg-[var(--primary)]" style={{ width: `${weightPercent}%` }} />
        </div>
      </div>
      <div className="rounded-lg border border-[var(--border)] bg-white p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">Goal limit</span>
          <span>{count} / 8 goals</span>
        </div>
        <div className="mt-3 h-2 rounded-full bg-[var(--secondary)]">
          <div className="h-2 rounded-full bg-emerald-600" style={{ width: `${countPercent}%` }} />
        </div>
      </div>
    </div>
  );
}

export default function GoalsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editGoalId, setEditGoalId] = useState<string | null>(null);
  const [achievementGoal, setAchievementGoal] = useState<Goal | null>(null);

  const { data: cycles, isLoading: loadingCycles } = useQuery({ queryKey: ["cycles"], queryFn: cycleApi.list });
  const activeCycle = cycles?.find((cycle: GoalCycle) => cycle.status === "ACTIVE");

  const { data: goals, isLoading: loadingGoals } = useQuery({
    queryKey: ["goals", activeCycle?.id],
    queryFn: () => goalApi.listMy(activeCycle!.id),
    enabled: !!activeCycle,
  });

  const { data: thrustAreas } = useQuery({
    queryKey: ["thrustAreas", activeCycle?.id],
    queryFn: () => thrustAreaApi.list(activeCycle!.id),
    enabled: !!activeCycle,
  });

  const submitMutation = useMutation({
    mutationFn: () => goalApi.submit(activeCycle!.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["goals"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => goalApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["goals"] }),
  });

  if (loadingCycles || loadingGoals) return <PageLoader />;
  if (!activeCycle) {
    return <EmptyState icon={<Target className="h-12 w-12" />} title="No active cycle" description="No goal cycle is currently active." />;
  }

  const goalList = goals ?? [];
  const totalWeightage = goalList.reduce((sum: number, goal: Goal) => sum + goal.weightage, 0);
  const canSubmit =
    goalList.length > 0 &&
    totalWeightage === 100 &&
    goalList.every((goal: Goal) => goal.status === GoalStatus.DRAFT || goal.status === GoalStatus.RETURNED);
  const hasReturned = goalList.some((goal: Goal) => goal.status === GoalStatus.RETURNED);
  const isReadOnly = goalList.some(
    (goal: Goal) => goal.status === GoalStatus.SUBMITTED || goal.status === GoalStatus.APPROVED || goal.status === GoalStatus.LOCKED,
  );

  return (
    <div className="space-y-5">
      <section className="app-panel rounded-lg p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="page-kicker">Employee goal sheet</p>
            <h2 className="mt-2 text-2xl font-semibold">{activeCycle.name}</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Build a measurable sheet with up to 8 goals, minimum 10% each, exactly 100% total weightage.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!isReadOnly && goalList.length < 8 && (
              <Button onClick={() => setShowCreate(true)}>
                <Plus className="h-4 w-4" />
                Add Goal
              </Button>
            )}
            <Button onClick={() => submitMutation.mutate()} disabled={!canSubmit || submitMutation.isPending} variant={canSubmit ? "default" : "outline"}>
              <Send className="h-4 w-4" />
              {submitMutation.isPending ? "Submitting..." : "Submit Sheet"}
            </Button>
          </div>
        </div>
        <div className="mt-5">
          <GoalProgressRail totalWeightage={totalWeightage} count={goalList.length} />
        </div>
      </section>

      {hasReturned && (
        <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-semibold">Goals returned for revision</p>
            <p className="mt-1 text-rose-700">Review manager feedback, adjust your goals, then submit the sheet again.</p>
          </div>
        </div>
      )}

      <Card className="app-panel">
        <CardContent className="p-0">
          {goalList.length === 0 ? (
            <div className="p-8">
              <EmptyState
                icon={<Target className="h-12 w-12" />}
                title="No goals created"
                description="Start by creating a weighted goal for this cycle."
                action={<Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4" />Create First Goal</Button>}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--secondary)] text-xs text-[var(--muted-foreground)]">
                  <tr>
                    <th className="px-5 py-3 font-medium">Goal</th>
                    <th className="px-5 py-3 font-medium">Measurement</th>
                    <th className="px-5 py-3 font-medium">Target</th>
                    <th className="px-5 py-3 font-medium">Weight</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] bg-white">
                  {goalList.map((goal: Goal) => {
                    const editable = goal.status === GoalStatus.DRAFT || goal.status === GoalStatus.RETURNED;
                    const trackable = goal.status === GoalStatus.APPROVED || goal.status === GoalStatus.LOCKED;
                    return (
                      <tr key={goal.id} className="align-top">
                        <td className="max-w-md px-5 py-4">
                          <p className="font-medium">{goal.title}</p>
                          <p className="mt-1 line-clamp-2 text-xs text-[var(--muted-foreground)]">{goal.description ?? "No description"}</p>
                          {goal.returned_reason && (
                            <p className="mt-2 rounded-md bg-rose-50 px-2 py-1 text-xs text-rose-700">{goal.returned_reason}</p>
                          )}
                        </td>
                        <td className="px-5 py-4 font-mono text-xs">{goal.uom_type.replace(/_/g, " ")}</td>
                        <td className="px-5 py-4 font-mono text-xs">{goal.target_date ?? goal.target_value ?? "N/A"}</td>
                        <td className="px-5 py-4 font-mono text-xs">{goal.weightage}%</td>
                        <td className="px-5 py-4"><StatusBadge status={goal.status} /></td>
                        <td className="px-5 py-4">
                          {editable ? (
                            <div className="flex justify-end gap-1">
                              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditGoalId(goal.id)} aria-label="Edit goal">
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-rose-600 hover:text-rose-700"
                                onClick={() => {
                                  if (confirm("Delete this goal?")) deleteMutation.mutate(goal.id);
                                }}
                                aria-label="Delete goal"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          ) : trackable ? (
                            <div className="flex justify-end">
                              <Button variant="outline" size="sm" onClick={() => setAchievementGoal(goal)}>
                                <Activity className="h-3.5 w-3.5" />
                                Actuals
                              </Button>
                            </div>
                          ) : (
                            <div className="flex justify-end text-xs text-[var(--muted-foreground)]">
                              <CheckCircle2 className="h-4 w-4" />
                            </div>
                          )}
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

      <AnimatePresence>
        {(showCreate || editGoalId) && (
          <GoalFormModal
            cycleId={activeCycle.id}
            goalId={editGoalId}
            thrustAreas={thrustAreas ?? []}
            onClose={() => {
              setShowCreate(false);
              setEditGoalId(null);
            }}
          />
        )}
        {achievementGoal && (
          <AchievementModal goal={achievementGoal} onClose={() => setAchievementGoal(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}

function AchievementModal({ goal, onClose }: { goal: Goal; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [quarter, setQuarter] = useState<Quarter>("Q1");
  const [plannedValue, setPlannedValue] = useState(goal.target_value ?? "");
  const [actualValue, setActualValue] = useState("");
  const [completionDate, setCompletionDate] = useState("");
  const [progress, setProgress] = useState<GoalProgress>("NOT_STARTED");
  const [error, setError] = useState("");

  const { data: achievements, isLoading } = useQuery({
    queryKey: ["achievements", goal.id],
    queryFn: () => achievementApi.list(goal.id),
  });

  const upsertMutation = useMutation({
    mutationFn: () =>
      achievementApi.upsert(goal.id, {
        quarter,
        planned_value: plannedValue || undefined,
        actual_value: actualValue || undefined,
        completion_date: completionDate || undefined,
        status: progress,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["achievements", goal.id] });
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      setActualValue("");
      setCompletionDate("");
      setProgress("NOT_STARTED");
      setError("");
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to save achievement update");
    },
  });

  const selected = achievements?.find((item: Achievement) => item.quarter === quarter);
  const targetLabel = goal.uom_type === "TIMELINE" ? goal.target_date : goal.target_value;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 16 }}
        className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl"
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="page-kicker">Quarterly achievement</p>
            <h2 className="mt-1 text-xl font-semibold">{goal.title}</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Target: {targetLabel ?? "N/A"} / {goal.uom_type.replace(/_/g, " ")} / {goal.weightage}% weight
            </p>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-[var(--muted-foreground)] hover:bg-[var(--secondary)]" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        {isLoading ? (
          <PageLoader />
        ) : (
          <div className="grid gap-5 lg:grid-cols-[1fr_0.95fr]">
            <div className="rounded-lg border border-[var(--border)]">
              <div className="border-b border-[var(--border)] px-4 py-3">
                <h3 className="text-sm font-semibold">Recorded actuals</h3>
              </div>
              {(achievements ?? []).length === 0 ? (
                <p className="px-4 py-8 text-center text-sm text-[var(--muted-foreground)]">No quarterly updates yet.</p>
              ) : (
                <div className="divide-y divide-[var(--border)]">
                  {(achievements ?? []).map((achievement: Achievement) => (
                    <button
                      key={achievement.id}
                      type="button"
                      onClick={() => {
                        setQuarter(achievement.quarter);
                        setPlannedValue(achievement.planned_value ?? "");
                        setActualValue(achievement.actual_value ?? "");
                        setCompletionDate(achievement.completion_date ?? "");
                        setProgress(achievement.status);
                      }}
                      className="grid w-full grid-cols-[56px_1fr_auto] items-center gap-3 px-4 py-3 text-left text-sm hover:bg-[var(--secondary)]"
                    >
                      <span className="rounded-md bg-[var(--secondary)] px-2 py-1 text-center font-mono text-xs">{achievement.quarter}</span>
                      <span>
                        <span className="block font-medium">{achievement.status.replace(/_/g, " ")}</span>
                        <span className="text-xs text-[var(--muted-foreground)]">
                          Actual {achievement.actual_value ?? "N/A"} / Planned {achievement.planned_value ?? "N/A"}
                        </span>
                      </span>
                      <span className="font-mono text-xs text-[var(--primary)]">{achievement.computed_score ?? "N/A"}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <form
              onSubmit={(event) => {
                event.preventDefault();
                upsertMutation.mutate();
              }}
              className="rounded-lg border border-[var(--border)] p-4"
            >
              <div className="grid gap-4">
                <div>
                  <label htmlFor="achievement-quarter" className="text-sm font-medium">Quarter</label>
                  <select
                    id="achievement-quarter"
                    value={quarter}
                    onChange={(event) => {
                      const nextQuarter = event.target.value as Quarter;
                      const next = achievements?.find((item: Achievement) => item.quarter === nextQuarter);
                      setQuarter(nextQuarter);
                      setPlannedValue(next?.planned_value ?? goal.target_value ?? "");
                      setActualValue(next?.actual_value ?? "");
                      setCompletionDate(next?.completion_date ?? "");
                      setProgress(next?.status ?? "NOT_STARTED");
                    }}
                    className="flex h-10 w-full rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                  >
                    {QUARTERS.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </div>

                {goal.uom_type === "TIMELINE" ? (
                  <div>
                    <label htmlFor="completion-date" className="text-sm font-medium">Completion date</label>
                    <Input id="completion-date" type="date" value={completionDate} onChange={(event) => setCompletionDate(event.target.value)} />
                  </div>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label htmlFor="planned-value" className="text-sm font-medium">Planned</label>
                      <Input id="planned-value" type="number" step="0.01" value={plannedValue} onChange={(event) => setPlannedValue(event.target.value)} />
                    </div>
                    <div>
                      <label htmlFor="actual-value" className="text-sm font-medium">Actual</label>
                      <Input id="actual-value" type="number" step="0.01" value={actualValue} onChange={(event) => setActualValue(event.target.value)} />
                    </div>
                  </div>
                )}

                <div>
                  <label htmlFor="achievement-status" className="text-sm font-medium">Status</label>
                  <select
                    id="achievement-status"
                    value={progress}
                    onChange={(event) => setProgress(event.target.value as GoalProgress)}
                    className="flex h-10 w-full rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                  >
                    {PROGRESS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>

                {selected?.computed_score && (
                  <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                    Current computed score: <span className="font-mono">{selected.computed_score}</span>
                  </div>
                )}

                {error && (
                  <div className="flex items-center gap-2 rounded-lg bg-rose-50 px-3 py-2.5 text-sm text-rose-700" role="alert">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                  </div>
                )}

                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={onClose}>Close</Button>
                  <Button type="submit" disabled={upsertMutation.isPending}>
                    {upsertMutation.isPending ? "Saving..." : "Save Actuals"}
                  </Button>
                </div>
              </div>
            </form>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}

interface GoalFormModalProps {
  cycleId: string;
  goalId: string | null;
  thrustAreas: { id: string; name: string }[];
  onClose: () => void;
}

function GoalFormModal({ cycleId, goalId, thrustAreas, onClose }: GoalFormModalProps) {
  const isEdit = !!goalId;
  const { data: existingGoal } = useQuery({
    queryKey: ["goal", goalId],
    queryFn: () => goalApi.get(goalId!),
    enabled: isEdit,
  });

  if (isEdit && !existingGoal) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
      >
        <div className="rounded-lg bg-white p-6 shadow-xl">
          <PageLoader />
        </div>
      </motion.div>
    );
  }

  return (
    <GoalFormFields
      cycleId={cycleId}
      goal={existingGoal ?? null}
      thrustAreas={thrustAreas}
      onClose={onClose}
    />
  );
}

function GoalFormFields({
  cycleId,
  goal,
  thrustAreas,
  onClose,
}: {
  cycleId: string;
  goal: Goal | null;
  thrustAreas: { id: string; name: string }[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const isEdit = !!goal;

  const [title, setTitle] = useState(goal?.title ?? "");
  const [description, setDescription] = useState(goal?.description ?? "");
  const [uomType, setUomType] = useState<UomType>(goal?.uom_type ?? "NUMERIC_MAX");
  const [targetValue, setTargetValue] = useState(goal?.target_value ?? "");
  const [targetDate, setTargetDate] = useState(goal?.target_date ?? "");
  const [weightage, setWeightage] = useState(String(goal?.weightage ?? 10));
  const [thrustAreaId, setThrustAreaId] = useState(goal?.thrust_area_id ?? "");
  const [error, setError] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof goalApi.create>[0]) => goalApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      onClose();
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to create goal";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: Parameters<typeof goalApi.update>[1]) => goalApi.update(goal!.id, data, goal!.version),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      onClose();
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to update goal";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    },
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    const payload = {
      title,
      description: description || undefined,
      uom_type: uomType,
      target_value: uomType !== "TIMELINE" ? targetValue || undefined : undefined,
      target_date: uomType === "TIMELINE" ? targetDate || undefined : undefined,
      weightage: Number.parseInt(weightage, 10),
      thrust_area_id: thrustAreaId || undefined,
    };

    if (isEdit) {
      updateMutation.mutate(payload);
    } else {
      createMutation.mutate({ ...payload, cycle_id: cycleId });
    }
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 16 }}
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl"
      >
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="page-kicker">{isEdit ? "Edit goal" : "New goal"}</p>
            <h2 className="mt-1 text-xl font-semibold">{isEdit ? "Update measurable target" : "Create measurable target"}</h2>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-[var(--muted-foreground)] hover:bg-[var(--secondary)]" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="grid gap-4">
          <div className="grid gap-4 md:grid-cols-[1.4fr_0.6fr]">
            <div>
              <label htmlFor="goal-title" className="text-sm font-medium">Title</label>
              <Input id="goal-title" value={title} onChange={(event) => setTitle(event.target.value)} required minLength={3} maxLength={300} placeholder="Increase enterprise renewal rate" />
            </div>
            <div>
              <label htmlFor="weightage" className="text-sm font-medium">Weightage</label>
              <Input id="weightage" type="number" min={10} max={100} value={weightage} onChange={(event) => setWeightage(event.target.value)} required />
            </div>
          </div>

          <div>
            <label htmlFor="goal-description" className="text-sm font-medium">Description</label>
            <textarea
              id="goal-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className="flex w-full rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              placeholder="Add context for manager review"
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label htmlFor="uom-type" className="text-sm font-medium">Measurement</label>
              <select id="uom-type" value={uomType} onChange={(event) => setUomType(event.target.value as UomType)} className="flex h-10 w-full rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
                {UOM_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="thrust-area" className="text-sm font-medium">Thrust area</label>
              <select id="thrust-area" value={thrustAreaId} onChange={(event) => setThrustAreaId(event.target.value)} className="flex h-10 w-full rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
                <option value="">Unassigned</option>
                {thrustAreas.map((area) => (
                  <option key={area.id} value={area.id}>{area.name}</option>
                ))}
              </select>
            </div>
          </div>

          {uomType === "TIMELINE" ? (
            <div>
              <label htmlFor="target-date" className="text-sm font-medium">Target date</label>
              <Input id="target-date" type="date" value={targetDate} onChange={(event) => setTargetDate(event.target.value)} required />
            </div>
          ) : (
            <div>
              <label htmlFor="target-value" className="text-sm font-medium">Target value</label>
              <Input id="target-value" type="number" step="0.01" value={targetValue} onChange={(event) => setTargetValue(event.target.value)} required placeholder="500000" />
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded-lg bg-rose-50 px-3 py-2.5 text-sm text-rose-700" role="alert">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={isPending}>{isPending ? "Saving..." : isEdit ? "Update Goal" : "Create Goal"}</Button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}
