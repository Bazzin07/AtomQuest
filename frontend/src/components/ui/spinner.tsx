import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SpinnerProps {
  className?: string;
  size?: number;
}

export function Spinner({ className, size = 20 }: SpinnerProps) {
  return (
    <Loader2
      className={cn("animate-spin text-[var(--muted-foreground)]", className)}
      size={size}
    />
  );
}

export function PageLoader() {
  return (
    <div className="flex h-64 items-center justify-center">
      <Spinner size={32} />
    </div>
  );
}

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 text-[var(--muted-foreground)]">{icon}</div>
      <h3 className="text-lg font-semibold text-[var(--foreground)]">
        {title}
      </h3>
      <p className="mt-1 max-w-sm text-sm text-[var(--muted-foreground)]">
        {description}
      </p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
