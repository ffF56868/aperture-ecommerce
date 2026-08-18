import { useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useMutation } from "@tanstack/react-query";
import { Aperture, ShieldCheck } from "lucide-react";
import { authApi } from "@/api/auth";
import { getErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { toast } from "@/store/toastStore";

const CODE_LENGTH = 6;

export function VerifyOtp() {
  const navigate = useNavigate();
  const location = useLocation();
  const phoneNumber = (location.state as { phoneNumber?: string } | null)?.phoneNumber;

  const [digits, setDigits] = useState<string[]>(Array(CODE_LENGTH).fill(""));
  const [error, setError] = useState<string | null>(null);
  const inputsRef = useRef<(HTMLInputElement | null)[]>([]);

  const mutation = useMutation({
    mutationFn: (code: string) => authApi.verifyOtp({ phone_number: phoneNumber!, code }),
    onSuccess: () => {
      toast.success("Phone verified — you can now sign in.");
      navigate("/login");
    },
    onError: (err) => setError(getErrorMessage(err, "Invalid or expired code.")),
  });

  const handleChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;
    const next = [...digits];
    next[index] = value.slice(-1);
    setDigits(next);
    setError(null);

    if (value && index < CODE_LENGTH - 1) {
      inputsRef.current[index + 1]?.focus();
    }
    if (next.every((d) => d !== "")) {
      mutation.mutate(next.join(""));
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
    }
  };

  if (!phoneNumber) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center gap-3 px-6 text-center">
        <p className="text-ink-muted">Start by creating an account to receive a verification code.</p>
        <Button onClick={() => navigate("/register")}>Go to registration</Button>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-sm text-center"
      >
        <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-accent/10">
          <ShieldCheck className="h-6 w-6 text-accent" />
        </div>
        <h1 className="font-display text-2xl font-semibold text-ink">Enter verification code</h1>
        <p className="mt-1 text-sm text-ink-muted">
          We sent a {CODE_LENGTH}-digit code to <span className="font-mono text-ink">{phoneNumber}</span>
        </p>

        <div className="mt-8 flex justify-center gap-2">
          {digits.map((digit, i) => (
            <input
              key={i}
              ref={(el) => {
                inputsRef.current[i] = el;
              }}
              value={digit}
              onChange={(e) => handleChange(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
              inputMode="numeric"
              maxLength={1}
              className="h-14 w-11 rounded-md border border-border-strong bg-bg-surface text-center font-mono text-xl text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent"
            />
          ))}
        </div>

        {error && <p className="mt-4 text-sm text-danger">{error}</p>}
        {mutation.isPending && <p className="mt-4 text-sm text-ink-muted">Verifying…</p>}

        <div className="mt-8 flex items-center justify-center gap-1.5 font-mono text-xs text-ink-faint">
          <Aperture className="h-3.5 w-3.5" />
          Codes expire after 2 minutes
        </div>
      </motion.div>
    </div>
  );
}
