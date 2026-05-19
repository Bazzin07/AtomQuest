import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { History, Search, ShieldCheck } from "lucide-react";
import { auditApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/spinner";
import type { AuditLog } from "@/types/api";

const ENTITY_TYPES = [
  { value: "", label: "All entities" },
  { value: "goal", label: "Goals" },
  { value: "achievement", label: "Achievements" },
  { value: "checkin_comment", label: "Check-in comments" },
  { value: "checkin_window", label: "Check-in windows" },
  { value: "escalation_rule", label: "Escalation rules" },
  { value: "escalation_log", label: "Escalation logs" },
] as const;

function humanize(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function summarize(values: Record<string, unknown> | null) {
  if (!values) return "No field snapshot";
  const entries = Object.entries(values).slice(0, 3);
  if (entries.length === 0) return "No field snapshot";
  return entries
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" / ");
}

export default function AuditPage() {
  const [entityType, setEntityType] = useState("");
  const [page, setPage] = useState(1);

  const { data: logs, isLoading } = useQuery({
    queryKey: ["auditLogs", entityType, page],
    queryFn: () => auditApi.list({ entity_type: entityType || undefined, page, size: 25 }),
  });

  if (isLoading) return <PageLoader />;

  const rows = logs ?? [];

  return (
    <div className="space-y-5">
      <section className="app-panel rounded-lg p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="page-kicker">Governance</p>
            <h2 className="mt-2 text-2xl font-semibold">Audit Trail</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Immutable change history for goals, windows, achievements, and escalation actions.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-xs text-[var(--muted-foreground)]">
            <ShieldCheck className="h-4 w-4 text-[var(--primary)]" />
            Post-lock accountability / who, what, when
          </div>
        </div>
      </section>

      <Card className="app-panel">
        <CardContent className="p-0">
          <div className="flex flex-col gap-3 border-b border-[var(--border)] px-5 py-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="font-semibold">Recent events</h3>
              <p className="text-sm text-[var(--muted-foreground)]">Filter by entity type and inspect field-level deltas.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-foreground)]" />
                <select
                  value={entityType}
                  onChange={(event) => {
                    setEntityType(event.target.value);
                    setPage(1);
                  }}
                  className="h-10 rounded-lg border border-[var(--input)] bg-white pl-9 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                >
                  {ENTITY_TYPES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {rows.length === 0 ? (
            <div className="p-8">
              <EmptyState
                icon={<History className="h-12 w-12" />}
                title="No audit events"
                description="Audit entries appear as users and admins change governed records."
              />
            </div>
          ) : (
            <div className="divide-y divide-[var(--border)] bg-white">
              {rows.map((log: AuditLog) => (
                <div key={log.id} className="grid gap-4 px-5 py-4 lg:grid-cols-[180px_180px_1fr]">
                  <div>
                    <p className="text-xs text-[var(--muted-foreground)]">Event</p>
                    <p className="mt-1 font-semibold">{humanize(log.action)}</p>
                    <p className="mt-1 text-xs text-[var(--muted-foreground)]">{humanize(log.entity_type)}</p>
                  </div>

                  <div>
                    <p className="text-xs text-[var(--muted-foreground)]">Actor</p>
                    <p className="mt-1 font-medium">{log.changed_by_name ?? log.changed_by.slice(0, 8)}</p>
                    <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                      {new Date(log.created_at).toLocaleString()}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="rounded-lg bg-[var(--secondary)] px-3 py-2 text-sm">
                      <p className="font-medium">Before</p>
                      <p className="mt-1 text-xs text-[var(--muted-foreground)]">{summarize(log.old_values)}</p>
                    </div>
                    <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm">
                      <p className="font-medium text-emerald-900">After</p>
                      <p className="mt-1 text-xs text-emerald-800">{summarize(log.new_values)}</p>
                    </div>
                    {log.reason && <p className="text-xs text-rose-700">Reason: {log.reason}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between border-t border-[var(--border)] px-5 py-4">
            <p className="text-xs text-[var(--muted-foreground)]">Page {page}</p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setPage((current) => Math.max(current - 1, 1))} disabled={page === 1}>
                Previous
              </Button>
              <Button variant="outline" size="sm" onClick={() => setPage((current) => current + 1)} disabled={rows.length < 25}>
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
