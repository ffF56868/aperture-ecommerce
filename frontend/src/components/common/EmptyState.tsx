import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ icon: Icon, title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border-strong py-20 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-white/[0.04]">
        <Icon className="h-6 w-6 text-ink-muted" strokeWidth={1.5} />
      </div>
      <div className="max-w-sm space-y-1">
        <h3 className="font-display text-lg font-semibold text-ink">{title}</h3>
        <p className="text-sm text-ink-muted">{description}</p>
      </div>
      {actionLabel && onAction && (
        <Button variant="secondary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
