import {
  forwardRef,
  type InputHTMLAttributes,
  type LabelHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "@/utils/cn";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, error, ...props }, ref) => (
  <div className="w-full">
    <input
      ref={ref}
      className={cn(
        "w-full h-11 rounded-md bg-bg-surface border px-3.5 text-sm text-ink placeholder:text-ink-faint",
        "transition-colors duration-150 outline-none",
        "focus:border-accent focus:ring-1 focus:ring-accent",
        error ? "border-danger" : "border-border-strong",
        className,
      )}
      {...props}
    />
    {error && <p className="mt-1.5 text-xs text-danger">{error}</p>}
  </div>
));
Input.displayName = "Input";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => (
    <div className="w-full">
      <textarea
        ref={ref}
        className={cn(
          "w-full min-h-[120px] rounded-md bg-bg-surface border px-3.5 py-3 text-sm text-ink placeholder:text-ink-faint",
          "transition-colors duration-150 outline-none resize-y",
          "focus:border-accent focus:ring-1 focus:ring-accent",
          error ? "border-danger" : "border-border-strong",
          className,
        )}
        {...props}
      />
      {error && <p className="mt-1.5 text-xs text-danger">{error}</p>}
    </div>
  ),
);
Textarea.displayName = "Textarea";

export const Label = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, children, ...props }, ref) => (
    <label
      ref={ref}
      className={cn("mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted", className)}
      {...props}
    >
      {children}
    </label>
  ),
);
Label.displayName = "Label";
