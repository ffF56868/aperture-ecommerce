import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Info, XCircle } from "lucide-react";
import { useToastStore } from "@/store/toastStore";
import { cn } from "@/utils/cn";

const icons = {
  success: CheckCircle2,
  error: XCircle,
  default: Info,
};

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[100] flex w-full max-w-sm flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => {
          const Icon = icons[t.variant];
          return (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 12, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.15 } }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              onClick={() => dismiss(t.id)}
              className={cn(
                "glass pointer-events-auto flex items-start gap-2.5 rounded-lg px-4 py-3 text-sm shadow-xl cursor-pointer",
                t.variant === "success" && "border-success/30",
                t.variant === "error" && "border-danger/30",
              )}
            >
              <Icon
                className={cn(
                  "mt-0.5 h-4 w-4 shrink-0",
                  t.variant === "success" && "text-success",
                  t.variant === "error" && "text-danger",
                  t.variant === "default" && "text-accent-soft",
                )}
              />
              <span className="text-ink">{t.message}</span>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
