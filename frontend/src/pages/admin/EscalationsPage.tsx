import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Pencil, Play, Plus, Shield, TimerReset, X } from "lucide-react";
import { cycleApi, escalationApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState, PageLoader } from "@/components/ui/spinner";
import type {
  EscalationEventType,
  EscalationLog,
  EscalationRule,
  EscalationRuleCreateRequest,
  GoalCycle,
} from "@/types/api";

const EVENT_OPTIONS: { value: EscalationEventType; label: string }[] = [
  { value: "GOALS_NOT_SUBMITTED", label: "Goals Not Submitted" },
  { value: "MANAGER_NOT_APPROVED", label: "Manager Not Approved" },
  { value: "CHECKIN_NOT_COMPLETED", label: "Check-in Not Completed" },
];

function humanize(value: string) {
  return value.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function EscalationsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editingRule, setEditingRule] = useState<EscalationRule | null>(null);
  const { data: cycles } = useQuery({ queryKey: ["cycles"], queryFn: cycleApi.list });
  const activeCycle = cycles?.find((cycle: GoalCycle) => cycle.status === "ACTIVE");

  const { data: rules, isLoading: loadingRules } = useQuery({
    queryKey: ["escalationRules"],
    queryFn: escalationApi.listRules,
  });

  const { data: logs, isLoading: loadingLogs } = useQuery({
    queryKey: ["escalationLogs", activeCycle?.id],
    queryFn: () => escalationApi.listLogs(activeCycle!.id),
    enabled: !!activeCycle,
  });

  const evaluateMutation = useMutation({
    mutationFn: () => escalationApi.evaluate(activeCycle!.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["escalationLogs"] }),
  });

  const resolveMutation = useMutation({
    mutationFn: (logId: string) => escalationApi.resolve(logId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["escalationLogs"] }),
  });

  if (loadingRules || loadingLogs) return <PageLoader />;

  const openLogs = (logs ?? []).filter((log: EscalationLog) => log.status === "OPEN");
  const resolvedLogs = (logs ?? []).filter((log: EscalationLog) => log.status === "RESOLVED");

  return (
    <div className="space-y-5">
      <section className="app-panel rounded-lg p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="page-kicker">Rule-based escalation</p>
            <h2 className="mt-2 text-2xl font-semibold">Escalations</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Review, resolve, and tune escalation rules for the active cycle.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setShowCreate((value) => !value)}>
              <Plus className="h-4 w-4" />
              Rule
            </Button>
            {activeCycle && (
              <Button onClick={() => evaluateMutation.mutate()} disabled={evaluateMutation.isPending}>
                <Play className="h-4 w-4" />
                {evaluateMutation.isPending ? "Evaluating..." : "Evaluate Now"}
              </Button>
            )}
          </div>
        </div>
      </section>

      {showCreate && (
        <RuleEditor
          title="Create Rule"
          submitLabel="Create"
          onCancel={() => setShowCreate(false)}
          onSubmit={async (payload) => {
            const createPayload = payload as EscalationRuleCreateRequest;
            await escalationApi.createRule(createPayload);
            setShowCreate(false);
            await queryClient.invalidateQueries({ queryKey: ["escalationRules"] });
          }}
        />
      )}

      {editingRule && (
        <RuleEditor
          title="Edit Rule"
          submitLabel="Save"
          initialRule={editingRule}
          onCancel={() => setEditingRule(null)}
          onSubmit={async (payload) => {
            await escalationApi.updateRule(editingRule.id, payload);
            setEditingRule(null);
            await queryClient.invalidateQueries({ queryKey: ["escalationRules"] });
          }}
        />
      )}

      <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <Card className="app-panel">
          <CardContent className="p-0">
            <div className="border-b border-[var(--border)] px-5 py-4">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-[var(--primary)]" />
                <h3 className="font-semibold">Configured Rules</h3>
              </div>
            </div>
            {(rules ?? []).length === 0 ? (
              <div className="p-5 text-sm text-[var(--muted-foreground)]">No escalation rules configured.</div>
            ) : (
              <div className="divide-y divide-[var(--border)]">
                {(rules ?? []).map((rule: EscalationRule) => (
                  <div key={rule.id} className="px-5 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold">{humanize(rule.event_type)}</p>
                        <p className="mt-1 text-xs text-[var(--muted-foreground)]">{rule.description}</p>
                      </div>
                      <span className={rule.is_active ? "rounded-md bg-emerald-50 px-2 py-1 text-xs text-emerald-700" : "rounded-md bg-zinc-100 px-2 py-1 text-xs text-zinc-500"}>
                        {rule.is_active ? "Active" : "Inactive"}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-[var(--muted-foreground)]">
                      <span className="rounded-md bg-[var(--secondary)] px-2 py-1">{rule.threshold_days} day threshold</span>
                      <span className="rounded-md bg-[var(--secondary)] px-2 py-1">Level {rule.escalation_level}</span>
                      <Button size="sm" variant="outline" onClick={() => setEditingRule(rule)}>
                        <Pencil className="h-3.5 w-3.5" />
                        Edit
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="app-panel">
          <CardContent className="p-0">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                <h3 className="font-semibold">Open Logs</h3>
              </div>
              <span className="rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-700">{openLogs.length} open</span>
            </div>
            {openLogs.length === 0 ? (
              <div className="p-8">
                <EmptyState icon={<CheckCircle2 className="h-10 w-10 text-emerald-600" />} title="All clear" description="No open escalations for the active cycle." />
              </div>
            ) : (
              <div className="divide-y divide-[var(--border)]">
                {openLogs.map((log: EscalationLog) => (
                  <div key={log.id} className="flex flex-col justify-between gap-3 px-5 py-4 md:flex-row md:items-center">
                    <div>
                      <p className="text-sm font-semibold">{humanize(log.event_type)}</p>
                      <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                        {log.detail ?? "No detail"} / Triggered {new Date(log.triggered_at).toLocaleDateString()}
                      </p>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => resolveMutation.mutate(log.id)} disabled={resolveMutation.isPending}>
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Resolve
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {resolvedLogs.length > 0 && (
        <Card className="app-panel">
          <CardContent className="p-0">
            <div className="flex items-center gap-2 border-b border-[var(--border)] px-5 py-4">
              <TimerReset className="h-4 w-4 text-[var(--muted-foreground)]" />
              <h3 className="font-semibold">Recently Resolved</h3>
            </div>
            <div className="divide-y divide-[var(--border)]">
              {resolvedLogs.slice(0, 8).map((log: EscalationLog) => (
                <div key={log.id} className="flex items-center justify-between px-5 py-3 text-sm">
                  <span>{humanize(log.event_type)}</span>
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {log.resolved_at ? new Date(log.resolved_at).toLocaleDateString() : "Resolved"}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function RuleEditor({
  title,
  submitLabel,
  initialRule,
  onCancel,
  onSubmit,
}: {
  title: string;
  submitLabel: string;
  initialRule?: EscalationRule | null;
  onCancel: () => void;
  onSubmit: (payload: {
    event_type: EscalationEventType;
    threshold_days: number;
    escalation_level: number;
    is_active: boolean;
    description?: string | null;
  } | {
    threshold_days?: number;
    escalation_level?: number;
    is_active?: boolean;
    description?: string | null;
  }) => Promise<void>;
}) {
  const [eventType, setEventType] = useState<EscalationEventType>(initialRule?.event_type ?? "GOALS_NOT_SUBMITTED");
  const [thresholdDays, setThresholdDays] = useState(String(initialRule?.threshold_days ?? 3));
  const [escalationLevel, setEscalationLevel] = useState(String(initialRule?.escalation_level ?? 1));
  const [description, setDescription] = useState(initialRule?.description ?? "");
  const [isActive, setIsActive] = useState(initialRule?.is_active ?? true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  return (
    <Card className="app-panel">
      <CardContent className="p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">{title}</h3>
            <p className="text-sm text-[var(--muted-foreground)]">Control event type, threshold, level, and active status.</p>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onCancel} aria-label="Close rule editor">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setSubmitting(true);
            setError("");
            try {
              if (initialRule) {
                await onSubmit({
                  threshold_days: Number.parseInt(thresholdDays, 10),
                  escalation_level: Number.parseInt(escalationLevel, 10),
                  is_active: isActive,
                  description: description || null,
                });
              } else {
                await onSubmit({
                  event_type: eventType,
                  threshold_days: Number.parseInt(thresholdDays, 10),
                  escalation_level: Number.parseInt(escalationLevel, 10),
                  is_active: isActive,
                  description: description || null,
                });
              }
            } catch (err) {
              const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
              setError(typeof detail === "string" ? detail : "Unable to save rule");
            } finally {
              setSubmitting(false);
            }
          }}
          className="grid gap-4 lg:grid-cols-[1fr_120px_120px_auto]"
        >
          <div className="grid gap-4 lg:col-span-4 lg:grid-cols-[1.1fr_140px_140px_auto]">
            <div>
              <label htmlFor="rule-event" className="text-sm font-medium">Event</label>
              <select
                id="rule-event"
                value={eventType}
                onChange={(event) => setEventType(event.target.value as EscalationEventType)}
                disabled={!!initialRule}
                className="mt-1 flex h-10 w-full rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] disabled:bg-[var(--secondary)]"
              >
                {EVENT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="rule-threshold" className="text-sm font-medium">Days</label>
              <Input id="rule-threshold" type="number" min={0} max={365} value={thresholdDays} onChange={(event) => setThresholdDays(event.target.value)} required />
            </div>
            <div>
              <label htmlFor="rule-level" className="text-sm font-medium">Level</label>
              <Input id="rule-level" type="number" min={1} max={5} value={escalationLevel} onChange={(event) => setEscalationLevel(event.target.value)} required />
            </div>
            <label className="mt-6 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} className="h-4 w-4" />
              Active
            </label>
          </div>

          <div className="lg:col-span-4">
            <label htmlFor="rule-description" className="text-sm font-medium">Description</label>
            <textarea
              id="rule-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className="mt-1 flex w-full rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              placeholder="Operational explanation for this rule"
            />
          </div>

          {error && <p className="lg:col-span-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

          <div className="lg:col-span-4 flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : submitLabel}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
