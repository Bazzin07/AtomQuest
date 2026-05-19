import { cn } from "@/lib/utils";
import type { GoalStatus } from "@/types/api";

const STATUS_CONFIG: Record<
  GoalStatus,
  { label: string; bg: string; text: string; dot: string }
> = {
  DRAFT: {
    label: "Draft",
    bg: "bg-zinc-100",
    text: "text-zinc-700",
    dot: "bg-zinc-400",
  },
  SUBMITTED: {
    label: "Submitted",
    bg: "bg-amber-50",
    text: "text-amber-700",
    dot: "bg-amber-500",
  },
  APPROVED: {
    label: "Approved",
    bg: "bg-sky-50",
    text: "text-sky-700",
    dot: "bg-sky-500",
  },
  RETURNED: {
    label: "Returned",
    bg: "bg-rose-50",
    text: "text-rose-700",
    dot: "bg-rose-500",
  },
  LOCKED: {
    label: "Locked",
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    dot: "bg-emerald-500",
  },
};

interface StatusBadgeProps {
  status: GoalStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        config.bg,
        config.text,
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} />
      {config.label}
    </span>
  );
}
