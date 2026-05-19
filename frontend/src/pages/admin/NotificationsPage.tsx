import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, Mail, MessageSquare, Send, ShieldAlert, Slash } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/spinner";
import type { NotificationLog } from "@/types/api";

const CHANNEL_OPTIONS = [
  { value: "", label: "All channels" },
  { value: "EMAIL", label: "Email" },
  { value: "TEAMS", label: "Teams" },
];

const EVENT_OPTIONS = [
  { value: "", label: "All events" },
  { value: "GOAL_SUBMITTED", label: "Goal Submitted" },
  { value: "GOAL_APPROVED", label: "Goal Approved" },
  { value: "GOAL_RETURNED", label: "Goal Returned" },
  { value: "GOAL_LOCKED", label: "Goal Locked" },
  { value: "ESCALATION_RAISED", label: "Escalation Raised" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All outcomes" },
  { value: "SENT", label: "Sent" },
  { value: "SKIPPED_NOT_CONFIGURED", label: "Skipped" },
  { value: "FAILED", label: "Failed" },
];

function humanize(value: string) {
  return value.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusClasses(status: NotificationLog["status"]) {
  if (status === "SENT") return "bg-emerald-50 text-emerald-700";
  if (status === "FAILED") return "bg-rose-50 text-rose-700";
  return "bg-zinc-100 text-zinc-600";
}

function channelIcon(channel: NotificationLog["channel"]) {
  return channel === "EMAIL" ? Mail : MessageSquare;
}

export default function NotificationsPage() {
  const [channel, setChannel] = useState("");
  const [eventType, setEventType] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["notificationLogs", channel, eventType, statusFilter, page],
    queryFn: () =>
      adminApi.notifications({
        channel: channel || undefined,
        event_type: eventType || undefined,
        status_filter: statusFilter || undefined,
        page,
        size: 25,
      }),
  });

  if (isLoading) return <PageLoader />;

  const rows = data ?? [];
  const sentCount = rows.filter((row) => row.status === "SENT").length;
  const skippedCount = rows.filter((row) => row.status === "SKIPPED_NOT_CONFIGURED").length;
  const failedCount = rows.filter((row) => row.status === "FAILED").length;

  return (
    <div className="space-y-5">
      <section className="app-panel rounded-lg p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="page-kicker">Notification audit</p>
            <h2 className="mt-2 text-2xl font-semibold">Delivery Activity</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Review email and Teams delivery attempts for goal workflow and escalation events.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-sm">
            <Metric label="Sent" value={sentCount} icon={Send} />
            <Metric label="Skipped" value={skippedCount} icon={Slash} />
            <Metric label="Failed" value={failedCount} icon={ShieldAlert} />
          </div>
        </div>
      </section>

      <Card className="app-panel">
        <CardContent className="p-0">
          <div className="flex flex-col gap-3 border-b border-[var(--border)] px-5 py-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="font-semibold">Recent attempts</h3>
              <p className="text-sm text-[var(--muted-foreground)]">Filter by channel, event, and delivery outcome.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <FilterSelect value={channel} onChange={(value) => { setChannel(value); setPage(1); }} options={CHANNEL_OPTIONS} />
              <FilterSelect value={eventType} onChange={(value) => { setEventType(value); setPage(1); }} options={EVENT_OPTIONS} />
              <FilterSelect value={statusFilter} onChange={(value) => { setStatusFilter(value); setPage(1); }} options={STATUS_OPTIONS} />
            </div>
          </div>

          {rows.length === 0 ? (
            <div className="p-8">
              <EmptyState icon={<Bell className="h-12 w-12" />} title="No delivery attempts" description="Notification logs appear after goal workflow and escalation events run." />
            </div>
          ) : (
            <div className="divide-y divide-[var(--border)] bg-white">
              {rows.map((row) => {
                const ChannelIcon = channelIcon(row.channel);
                return (
                  <div key={row.id} className="grid gap-4 px-5 py-4 lg:grid-cols-[200px_1fr_160px]">
                    <div>
                      <div className="flex items-center gap-2">
                        <ChannelIcon className="h-4 w-4 text-[var(--primary)]" />
                        <p className="font-medium">{humanize(row.channel)}</p>
                      </div>
                      <p className="mt-1 text-xs text-[var(--muted-foreground)]">{humanize(row.event_type)}</p>
                    </div>

                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{row.subject}</p>
                      <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                        {row.recipient_email ?? "No recipient"} / {new Date(row.attempted_at).toLocaleString()}
                      </p>
                      <p className="mt-2 text-sm text-[var(--muted-foreground)]">{row.detail ?? "No detail provided."}</p>
                      {row.error_message && (
                        <p className="mt-2 text-xs text-rose-700">Error: {row.error_message}</p>
                      )}
                    </div>

                    <div className="flex items-start justify-between gap-3 lg:justify-end">
                      <span className={`rounded-md px-2 py-1 text-xs font-medium ${statusClasses(row.status)}`}>
                        {humanize(row.status)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="flex items-center justify-between border-t border-[var(--border)] px-5 py-4">
            <p className="text-xs text-[var(--muted-foreground)]">Page {page}</p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setPage((current) => Math.max(current - 1, 1))}
                disabled={page === 1}
                className="rounded-md border border-[var(--border)] px-3 py-2 text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage((current) => current + 1)}
                disabled={rows.length < 25}
                className="rounded-md border border-[var(--border)] px-3 py-2 text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function FilterSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-10 rounded-lg border border-[var(--input)] bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: React.ElementType }) {
  return (
    <div className="rounded-lg bg-white/80 px-3 py-2">
      <div className="flex items-center justify-center gap-1 text-[var(--muted-foreground)]">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-xs">{label}</span>
      </div>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}
