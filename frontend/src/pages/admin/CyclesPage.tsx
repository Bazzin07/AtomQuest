import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Calendar, Clock3, Layers3, Pencil, Plus, Settings } from "lucide-react";
import { adminApi, checkinApi, cycleApi, thrustAreaApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState, PageLoader } from "@/components/ui/spinner";
import type { CheckinWindow, GoalCycle, Quarter, ThrustArea } from "@/types/api";

const QUARTERS: Quarter[] = ["Q1", "Q2", "Q3", "Q4"];

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

export default function CyclesPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [thrustAreaName, setThrustAreaName] = useState("");
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null);
  const [windowQuarter, setWindowQuarter] = useState<Quarter>("Q1");
  const [windowOpen, setWindowOpen] = useState("");
  const [windowClose, setWindowClose] = useState("");
  const [editingWindowId, setEditingWindowId] = useState<string | null>(null);

  const { data: cycles, isLoading } = useQuery({ queryKey: ["cycles"], queryFn: cycleApi.list });

  const activeCycle = cycles?.find((cycle: GoalCycle) => cycle.status === "ACTIVE");
  const selectedCycle = cycles?.find((cycle: GoalCycle) => cycle.id === selectedCycleId) ?? activeCycle ?? null;

  const { data: thrustAreas } = useQuery({
    queryKey: ["thrustAreas", selectedCycle?.id],
    queryFn: () => thrustAreaApi.list(selectedCycle!.id),
    enabled: !!selectedCycle,
  });

  const { data: windows } = useQuery({
    queryKey: ["checkinWindows", selectedCycle?.id],
    queryFn: () => checkinApi.windows(selectedCycle!.id),
    enabled: !!selectedCycle,
  });

  const createCycleMutation = useMutation({
    mutationFn: cycleApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cycles"] });
      setShowCreate(false);
      setName("");
      setStartDate("");
      setEndDate("");
    },
  });

  const createThrustAreaMutation = useMutation({
    mutationFn: thrustAreaApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["thrustAreas"] });
      setThrustAreaName("");
    },
  });

  const createWindowMutation = useMutation({
    mutationFn: adminApi.createCheckinWindow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["checkinWindows"] });
      setWindowQuarter("Q1");
      setWindowOpen("");
      setWindowClose("");
    },
  });

  const updateWindowMutation = useMutation({
    mutationFn: ({ id, opens_at, closes_at }: { id: string; opens_at: string; closes_at: string }) =>
      adminApi.updateCheckinWindow(id, { opens_at, closes_at }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["checkinWindows"] });
      setEditingWindowId(null);
    },
  });

  if (isLoading) return <PageLoader />;

  const cycleList = cycles ?? [];

  return (
    <div className="space-y-5">
      <section className="app-panel rounded-lg p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="page-kicker">Admin setup</p>
            <h2 className="mt-2 text-2xl font-semibold">Cycle Management</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Manage annual cycles, fixed quarterly windows, and thrust areas used by employee goal sheets.
            </p>
          </div>
          <Button onClick={() => setShowCreate((value) => !value)}>
            <Plus className="h-4 w-4" />
            New Cycle
          </Button>
        </div>
      </section>

      {showCreate && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="app-panel">
            <CardContent className="p-5">
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  createCycleMutation.mutate({ name, start_date: startDate, end_date: endDate });
                }}
                className="grid gap-4 lg:grid-cols-[1fr_180px_180px_auto] lg:items-end"
              >
                <div>
                  <label htmlFor="cycle-name" className="text-sm font-medium">Name</label>
                  <Input id="cycle-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="FY 2027 Goal Cycle" required />
                </div>
                <div>
                  <label htmlFor="start-date" className="text-sm font-medium">Start</label>
                  <Input id="start-date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} required />
                </div>
                <div>
                  <label htmlFor="end-date" className="text-sm font-medium">End</label>
                  <Input id="end-date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} required />
                </div>
                <Button type="submit" disabled={createCycleMutation.isPending}>
                  {createCycleMutation.isPending ? "Creating..." : "Create"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {cycleList.length === 0 ? (
        <EmptyState icon={<Calendar className="h-12 w-12" />} title="No cycles" description="Create your first goal cycle to get started." />
      ) : (
        <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
          <Card className="app-panel">
            <CardContent className="p-0">
              <div className="border-b border-[var(--border)] px-5 py-4">
                <h3 className="font-semibold">Goal cycles</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-[var(--secondary)] text-xs text-[var(--muted-foreground)]">
                    <tr>
                      <th className="px-5 py-3 font-medium">Cycle</th>
                      <th className="px-5 py-3 font-medium">Timeline</th>
                      <th className="px-5 py-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)] bg-white">
                    {cycleList.map((cycle: GoalCycle) => (
                      <tr
                        key={cycle.id}
                        onClick={() => setSelectedCycleId(cycle.id)}
                        className={`cursor-pointer transition-colors hover:bg-[var(--secondary)] ${selectedCycle?.id === cycle.id ? "bg-emerald-50/60" : ""}`}
                      >
                        <td className="px-5 py-4">
                          <p className="font-medium">{cycle.name}</p>
                          <p className="text-xs text-[var(--muted-foreground)]">{cycle.id.slice(0, 8)}</p>
                        </td>
                        <td className="px-5 py-4 text-xs text-[var(--muted-foreground)]">
                          {formatDate(cycle.start_date)} to {formatDate(cycle.end_date)}
                        </td>
                        <td className="px-5 py-4">
                          <span className={cycle.status === "ACTIVE" ? "rounded-md bg-emerald-50 px-2 py-1 text-xs text-emerald-700" : "rounded-md bg-zinc-100 px-2 py-1 text-xs text-zinc-600"}>
                            {cycle.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <div className="space-y-5">
            <Card className="app-panel">
              <CardContent className="p-0">
                <div className="border-b border-[var(--border)] px-5 py-4">
                  <div className="flex items-center gap-2">
                    <Layers3 className="h-4 w-4 text-[var(--primary)]" />
                    <h3 className="font-semibold">Thrust areas</h3>
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">{selectedCycle?.name ?? "Select a cycle"}</p>
                </div>
                <div className="p-5">
                  {(thrustAreas ?? []).length === 0 ? (
                    <p className="rounded-lg bg-[var(--secondary)] px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">No thrust areas yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {(thrustAreas ?? []).map((area: ThrustArea) => (
                        <div key={area.id} className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm">
                          <Settings className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
                          <span className="font-medium">{area.name}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {selectedCycle && (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        createThrustAreaMutation.mutate({ name: thrustAreaName, cycle_id: selectedCycle.id });
                      }}
                      className="mt-4 flex gap-2"
                    >
                      <Input value={thrustAreaName} onChange={(event) => setThrustAreaName(event.target.value)} placeholder="New thrust area" required />
                      <Button type="submit" disabled={createThrustAreaMutation.isPending}>Add</Button>
                    </form>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card className="app-panel">
              <CardContent className="p-0">
                <div className="border-b border-[var(--border)] px-5 py-4">
                  <div className="flex items-center gap-2">
                    <Clock3 className="h-4 w-4 text-[var(--primary)]" />
                    <h3 className="font-semibold">Check-in windows</h3>
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">{selectedCycle?.name ?? "Select a cycle"}</p>
                </div>
                <div className="p-5">
                  {(windows ?? []).length === 0 ? (
                    <p className="rounded-lg bg-[var(--secondary)] px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">No windows yet.</p>
                  ) : (
                    <div className="space-y-3">
                      {(windows ?? []).map((window) => (
                        <CheckinWindowRow
                          key={window.id}
                          window={window}
                          editing={editingWindowId === window.id}
                          onEdit={() => setEditingWindowId(window.id)}
                          onCancel={() => setEditingWindowId(null)}
                          onSave={(opens_at, closes_at) =>
                            updateWindowMutation.mutate({ id: window.id, opens_at, closes_at })
                          }
                          saving={updateWindowMutation.isPending && editingWindowId === window.id}
                        />
                      ))}
                    </div>
                  )}

                  {selectedCycle && (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        createWindowMutation.mutate({
                          cycle_id: selectedCycle.id,
                          quarter: windowQuarter,
                          opens_at: windowOpen,
                          closes_at: windowClose,
                        });
                      }}
                      className="mt-4 grid gap-3 md:grid-cols-[120px_1fr_1fr_auto]"
                    >
                      <select
                        value={windowQuarter}
                        onChange={(event) => setWindowQuarter(event.target.value as Quarter)}
                        className="h-10 rounded-lg border border-[var(--input)] bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                      >
                        {QUARTERS.filter((quarter) => !(windows ?? []).some((window) => window.quarter === quarter)).map((quarter) => (
                          <option key={quarter} value={quarter}>
                            {quarter}
                          </option>
                        ))}
                      </select>
                      <Input type="date" value={windowOpen} onChange={(event) => setWindowOpen(event.target.value)} required />
                      <Input type="date" value={windowClose} onChange={(event) => setWindowClose(event.target.value)} required />
                      <Button type="submit" disabled={createWindowMutation.isPending || QUARTERS.every((quarter) => (windows ?? []).some((window) => window.quarter === quarter))}>
                        Add
                      </Button>
                    </form>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function CheckinWindowRow({
  window,
  editing,
  saving,
  onEdit,
  onCancel,
  onSave,
}: {
  window: CheckinWindow;
  editing: boolean;
  saving: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSave: (opens_at: string, closes_at: string) => void;
}) {
  const [opensAt, setOpensAt] = useState(window.opens_at);
  const [closesAt, setClosesAt] = useState(window.closes_at);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-medium">{window.quarter}</p>
          <p className="text-xs text-[var(--muted-foreground)]">
            {formatDate(window.opens_at)} to {formatDate(window.closes_at)}
          </p>
        </div>
        {!editing ? (
          <Button size="sm" variant="outline" onClick={onEdit}>
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={onCancel}>Cancel</Button>
            <Button size="sm" onClick={() => onSave(opensAt, closesAt)} disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </Button>
          </div>
        )}
      </div>

      {editing && (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <Input type="date" value={opensAt} onChange={(event) => setOpensAt(event.target.value)} />
          <Input type="date" value={closesAt} onChange={(event) => setClosesAt(event.target.value)} />
        </div>
      )}
    </div>
  );
}
