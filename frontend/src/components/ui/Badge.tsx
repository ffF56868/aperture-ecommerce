import type { HTMLAttributes } from "react";
import { cn } from "@/utils/cn";

type Variant = "default" | "accent" | "coral" | "success" | "danger" | "outline";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

const variantClasses: Record<Variant, string> = {
  default: "bg-white/[0.06] text-ink-muted border-border",
  accent: "bg-accent/10 text-accent-soft border-accent/25",
  coral: "bg-coral/10 text-coral-soft border-coral/25",
  success: "bg-success/10 text-success border-success/25",
  danger: "bg-danger/10 text-danger border-danger/25",
  outline: "bg-transparent text-ink-muted border-border-strong",
};

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-mono uppercase tracking-wider",
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
