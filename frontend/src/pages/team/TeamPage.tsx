import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle, Filter, Lock, Pencil, RotateCcw, Share2, UnlockKeyhole, Users, X } from "lucide-react";
import { adminApi, cycleApi, goalApi, thrustAreaApi, userApi } from "@/api/endpoints";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState, PageLoader } from "@/components/ui/spinner";
import { useAuthStore } from "@/stores/auth";
import { GoalStatus, type Goal, type GoalCycle, type ThrustArea, type UomType, type User } from "@/types/api";

const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "SUBMITTED", label: "Pending" },
  { value: "APPROVED", label: "Approved" },
  { value: "LOCKED", label: "Locked" },
  { value: "RETURNED", label: "Returned" },
  { value: "DRAFT", label: "Draft" },
] as const;

const UOM_OPTIONS: { value: UomType; label: string }[] = [
  { value: "NUMERIC_MAX", label: "Numeric / higher is better" },
  { value: "NUMERIC_MIN", label: "Numeric / lower is better" },
  { value: "PERCENTAGE_MAX", label: "Percentage / higher" },
  { value: "PERCENTAGE_MIN", label: "Percentage / lower" },
  { value: "TIMELINE", label: "Timeline / deadline" },
  { value: "ZERO", label: "Zero target" },
];

export default function TeamPage() {
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user)!;
  const [statusFilter, setStatusFilter] = useState("");
  const [returnGoalId, setReturnGoalId] = useState<string | null>(null);
  const [returnReason, setReturnReason] = useState("");
  const [editGoal, setEditGoal] = useState<Goal | null>(null);
  const [showSharedGoal, setShowSharedGoal] = useState(false);

  const { data: cycles, isLoading: loadingCycles } = useQuery({ queryKey: ["cycles"], queryFn: cycleApi.list });
  const activeCycle = cycles?.find((cycle: GoalCycle) => cycle.status === "ACTIVE");

  const { data: teamGoals, isLoading: loadingGoals } = useQuery({
    queryKey: ["teamGoals", activeCycle?.id],
    queryFn: () => goalApi.listTeam(activeCycle!.id),
    enabled: !!activeCycle,
  });

  const { data: teamUsers } = useQuery({
    queryKey: ["teamUsers"],
    queryFn: userApi.team,
  });

  const { data: thrustAreas } = useQuery({
    queryKey: ["thrustAreas", activeCycle?.id],
    queryFn: () => thrustAreaApi.list(activeCycle!.id),
    enabled: !!activeCycle,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => goalApi.approve(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["teamGoals"] }),
  });

  const lockMutation = useMutation({
    mutationFn: (id: string) => goalApi.lock(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["teamGoals"] }),
  });

  const returnMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => goalApi.returnGoal(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teamGoals"] });
      setReturnGoalId(null);
      setReturnReason("");
    },
  });

  const unlockMutation = useMutation({
    mutationFn: (id: string) => adminApi.unlockGoal(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["teamGoals"] }),
  });

  if (loadingCycles || loadingGoals) return <PageLoader />;
  if (!activeCycle) {
    return <EmptyState icon={<Users className="h-12 w-12" />} title="No active cycle" description="There is no active goal cycle." />;
  }

  const goals = teamGoals ?? [];
  const filtered = statusFilter ? goals.filter((goal: Goal) => goal.status === statusFilter) : goals;
  const pending = goals.filter((goal: Goal) => goal.status === GoalStatus.SUBMITTED).length;

  return (
    <div className="space-y-5">
      <section className="app-panel rounded-lg p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="page-kicker">Manager workspace</p>
            <h2 className="mt-2 text-2xl font-semibold">Team Review</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Review submitted goals, edit targets inline, push shared KPIs, and lock final goals.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <Button onClick={() => setShowSharedGoal(true)} disabled={!activeCycle}>
              <Share2 className="h-4 w-4" />
              Shared KPI
            </Button>
            <div className="grid grid-cols-3 gap-2 text-center text-sm">
              <div className="rounded-lg bg-white px-4 py-3">
                <p className="font-semibold tabular-nums">{goals.length}</p>
                <p className="text-xs text-[var(--muted-foreground)]">Goals</p>
              </div>
              <div className="rounded-lg bg-amber-50 px-4 py-3 text-amber-800">
                <p className="font-semibold tabular-nums">{pending}</p>
                <p className="text-xs">Pending</p>
              </div>
              <div className="rounded-lg bg-emerald-50 px-4 py-3 text-emerald-800">
                <p className="font-semibold tabular-nums">{goals.filter((goal: Goal) => goal.status === GoalStatus.LOCKED).length}</p>
                <p className="text-xs">Locked</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <Card className="app-panel">
        <CardContent className="p-0">
          <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border)] px-5 py-4">
            <Filter className="h-4 w-4 text-[var(--muted-foreground)]" />
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter.value}
                onClick={() => setStatusFilter(filter.value)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  statusFilter === filter.value
                    ? "bg-[var(--primary)] text-white"
                    : "bg-[var(--secondary)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>

          {filtered.length === 0 ? (
            <div className="p-8">
              <EmptyState icon={<Users className="h-12 w-12" />} title="No goals found" description={statusFilter ? "No goals match this filter." : "Your team members have not created any goals yet."} />
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
                    <th className="px-5 py-3 text-right font-medium">Decision</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] bg-white">
                  {filtered.map((goal: Goal) => (
                    <tr key={goal.id} className="align-top">
                      <td className="max-w-md px-5 py-4">
                        <p className="font-medium">{goal.title}</p>
                        <p className="mt-1 line-clamp-2 text-xs text-[var(--muted-foreground)]">{goal.description ?? "No description"}</p>
                      </td>
                      <td className="px-5 py-4 font-mono text-xs">{goal.uom_type.replace(/_/g, " ")}</td>
                      <td className="px-5 py-4 font-mono text-xs">{goal.target_date ?? goal.target_value ?? "N/A"}</td>
                      <td className="px-5 py-4 font-mono text-xs">{goal.weightage}%</td>
                      <td className="px-5 py-4"><StatusBadge status={goal.status} /></td>
                      <td className="px-5 py-4">
                        <div className="flex justify-end gap-2">
                          {goal.status === GoalStatus.SUBMITTED && (
                            <>
                              <Button size="sm" variant="outline" onClick={() => setEditGoal(goal)}>
                                <Pencil className="h-3.5 w-3.5" />
                                Edit
                              </Button>
                              <Button size="sm" onClick={() => approveMutation.mutate(goal.id)} disabled={approveMutation.isPending}>
                                <CheckCircle className="h-3.5 w-3.5" />
                                Approve
                              </Button>
                              <Button size="sm" variant="outline" onClick={() => setReturnGoalId(goal.id)} className="text-rose-700 hover:bg-rose-50">
                                <RotateCcw className="h-3.5 w-3.5" />
                                Return
                              </Button>
                            </>
                          )}
                          {goal.status === GoalStatus.APPROVED && (
                            <Button size="sm" onClick={() => lockMutation.mutate(goal.id)} disabled={lockMutation.isPending}>
                              <Lock className="h-3.5 w-3.5" />
                              Lock
                            </Button>
                          )}
                          {user.role === "ADMIN" && goal.status === GoalStatus.LOCKED && (
                            <Button size="sm" variant="outline" onClick={() => unlockMutation.mutate(goal.id)} disabled={unlockMutation.isPending}>
                              <UnlockKeyhole className="h-3.5 w-3.5" />
                              Unlock
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <AnimatePresence>
        {showSharedGoal && activeCycle && (
          <SharedGoalModal
            cycleId={activeCycle.id}
            teamUsers={teamUsers ?? []}
            thrustAreas={thrustAreas ?? []}
            onClose={() => setShowSharedGoal(false)}
          />
        )}
        {editGoal && (
          <ManagerEditModal goal={editGoal} onClose={() => setEditGoal(null)} />
        )}
        {returnGoalId && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
            onClick={(event) => event.target === event.currentTarget && setReturnGoalId(null)}
          >
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }} className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="page-kicker text-rose-700">Return goal</p>
                  <h3 className="mt-1 text-lg font-semibold">Manager feedback</h3>
                </div>
                <button onClick={() => setReturnGoalId(null)} className="rounded-md p-1 text-[var(--muted-foreground)] hover:bg-[var(--secondary)]" aria-label="Close">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <textarea
                value={returnReason}
                onChange={(event) => setReturnReason(event.target.value)}
                rows={4}
                className="flex w-full rounded-lg border border-rose-200 bg-rose-50/60 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
                placeholder="Target or weightage needs revision..."
                required
                minLength={3}
              />
              <div className="mt-4 flex justify-end gap-2">
                <Button variant="outline" onClick={() => setReturnGoalId(null)}>Cancel</Button>
                <Button
                  onClick={() => returnMutation.mutate({ id: returnGoalId, reason: returnReason })}
                  disabled={returnReason.length < 3 || returnMutation.isPending}
                  className="bg-rose-700 hover:bg-rose-800"
                >
                  {returnMutation.isPending ? "Returning..." : "Return Goal"}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ManagerEditModal({ goal, onClose }: { goal: Goal; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [targetValue, setTargetValue] = useState(goal.target_value ?? "");
  const [targetDate, setTargetDate] = useState(goal.target_date ?? "");
  const [weightage, setWeightage] = useState(String(goal.weightage));
  const [error, setError] = useState("");

  const editMutation = useMutation({
    mutationFn: () =>
      goalApi.managerEdit(goal.id, {
        target_value: goal.uom_type === "TIMELINE" ? undefined : targetValue || undefined,
        target_date: goal.uom_type === "TIMELINE" ? targetDate || undefined : undefined,
        weightage: Number.parseInt(weightage, 10),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teamGoals"] });
      onClose();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to edit goal");
    },
  });

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }} className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <p className="page-kicker">Inline manager edit</p>
            <h3 className="mt-1 text-lg font-semibold">{goal.title}</h3>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">Only submitted goals can be edited before approval.</p>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-[var(--muted-foreground)] hover:bg-[var(--secondary)]" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid gap-4">
          {goal.uom_type === "TIMELINE" ? (
            <div>
              <label htmlFor="manager-target-date" className="text-sm font-medium">Target date</label>
              <Input id="manager-target-date" type="date" value={targetDate} onChange={(event) => setTargetDate(event.target.value)} />
            </div>
          ) : (
            <div>
              <label htmlFor="manager-target-value" className="text-sm font-medium">Target value</label>
              <Input id="manager-target-value" type="number" step="0.01" value={targetValue} onChange={(event) => setTargetValue(event.target.value)} />
            </div>
          )}
          <div>
            <label htmlFor="manager-weightage" className="text-sm font-medium">Weightage</label>
            <Input id="manager-weightage" type="number" min={10} max={100} value={weightage} onChange={(event) => setWeightage(event.target.value)} />
          </div>
          {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={() => editMutation.mutate()} disabled={editMutation.isPending}>
              {editMutation.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

function SharedGoalModal({
  cycleId,
  teamUsers,
  thrustAreas,
  onClose,
}: {
  cycleId: string;
  teamUsers: User[];
  thrustAreas: ThrustArea[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [uomType, setUomType] = useState<UomType>("NUMERIC_MAX");
  const [targetValue, setTargetValue] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [weightage, setWeightage] = useState("10");
  const [thrustAreaId, setThrustAreaId] = useState("");
  const [employeeIds, setEmployeeIds] = useState<string[]>([]);
  const [error, setError] = useState("");

  const sharedMutation = useMutation({
    mutationFn: () =>
      goalApi.createShared({
        cycle_id: cycleId,
        title,
        description: description || undefined,
        uom_type: uomType,
        target_value: uomType === "TIMELINE" ? undefined : targetValue || undefined,
        target_date: uomType === "TIMELINE" ? targetDate || undefined : undefined,
        weightage: Number.parseInt(weightage, 10),
        thrust_area_id: thrustAreaId || undefined,
        employee_ids: employeeIds,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teamGoals"] });
      onClose();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create shared KPI");
    },
  });

  const toggleEmployee = (employeeId: string) => {
    setEmployeeIds((current) =>
      current.includes(employeeId)
        ? current.filter((id) => id !== employeeId)
        : [...current, employeeId],
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }} className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="page-kicker">Shared goal</p>
            <h3 className="mt-1 text-xl font-semibold">Push shared KPI</h3>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">Recipients can edit weightage only. The source achievement syncs linked sheets.</p>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-[var(--muted-foreground)] hover:bg-[var(--secondary)]" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid gap-5 lg:grid-cols-[1fr_0.85fr]">
          <div className="grid gap-4">
            <div>
              <label htmlFor="shared-title" className="text-sm font-medium">Title</label>
              <Input id="shared-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Improve cross-sell conversion" required />
            </div>
            <div>
              <label htmlFor="shared-description" className="text-sm font-medium">Description</label>
              <textarea
                id="shared-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
                className="flex w-full rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                placeholder="Shared KPI context"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="shared-uom" className="text-sm font-medium">Measurement</label>
                <select id="shared-uom" value={uomType} onChange={(event) => setUomType(event.target.value as UomType)} className="flex h-10 w-full rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
                  {UOM_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="shared-weightage" className="text-sm font-medium">Default weightage</label>
                <Input id="shared-weightage" type="number" min={10} max={100} value={weightage} onChange={(event) => setWeightage(event.target.value)} />
              </div>
            </div>
            {uomType === "TIMELINE" ? (
              <div>
                <label htmlFor="shared-target-date" className="text-sm font-medium">Target date</label>
                <Input id="shared-target-date" type="date" value={targetDate} onChange={(event) => setTargetDate(event.target.value)} />
              </div>
            ) : (
              <div>
                <label htmlFor="shared-target-value" className="text-sm font-medium">Target value</label>
                <Input id="shared-target-value" type="number" step="0.01" value={targetValue} onChange={(event) => setTargetValue(event.target.value)} />
              </div>
            )}
            <div>
              <label htmlFor="shared-thrust" className="text-sm font-medium">Thrust area</label>
              <select id="shared-thrust" value={thrustAreaId} onChange={(event) => setThrustAreaId(event.target.value)} className="flex h-10 w-full rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
                <option value="">Unassigned</option>
                {thrustAreas.map((area) => <option key={area.id} value={area.id}>{area.name}</option>)}
              </select>
            </div>
          </div>

          <div className="rounded-lg border border-[var(--border)]">
            <div className="border-b border-[var(--border)] px-4 py-3">
              <p className="text-sm font-semibold">Recipients</p>
              <p className="text-xs text-[var(--muted-foreground)]">{employeeIds.length} selected</p>
            </div>
            <div className="max-h-80 divide-y divide-[var(--border)] overflow-y-auto">
              {teamUsers.length === 0 ? (
                <p className="px-4 py-8 text-center text-sm text-[var(--muted-foreground)]">No employees available.</p>
              ) : (
                teamUsers.map((employee) => (
                  <label key={employee.id} className="flex cursor-pointer items-center gap-3 px-4 py-3 text-sm hover:bg-[var(--secondary)]">
                    <input
                      type="checkbox"
                      checked={employeeIds.includes(employee.id)}
                      onChange={() => toggleEmployee(employee.id)}
                      className="h-4 w-4"
                    />
                    <span>
                      <span className="block font-medium">{employee.name}</span>
                      <span className="text-xs text-[var(--muted-foreground)]">{employee.department ?? "Unassigned"}</span>
                    </span>
                  </label>
                ))
              )}
            </div>
          </div>
        </div>

        {error && <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            onClick={() => sharedMutation.mutate()}
            disabled={sharedMutation.isPending || title.length < 3 || employeeIds.length === 0}
          >
            {sharedMutation.isPending ? "Creating..." : "Create Shared KPI"}
          </Button>
        </div>
      </motion.div>
    </motion.div>
  );
}
