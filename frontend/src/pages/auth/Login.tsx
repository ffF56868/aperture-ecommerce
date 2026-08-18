import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Aperture, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Input";
import { useAuth } from "@/hooks/useAuth";

export function Login() {
  const { login, isLoggingIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login({ username, password });
  };

  return (
    <div className="grid min-h-[calc(100vh-4rem)] md:grid-cols-2">
      <div className="relative hidden overflow-hidden border-r border-border bg-bg-surface md:flex md:flex-col md:justify-between md:p-12">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.4]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />
        <Aperture className="relative h-8 w-8 text-accent" />
        <div className="relative">
          <p className="max-w-sm font-display text-2xl font-semibold leading-snug text-ink">
            "Every order arrives exactly as specced. That's the whole promise."
          </p>
          <p className="mt-3 font-mono text-xs text-ink-faint">— Aperture Quality Standard</p>
        </div>
      </div>

      <div className="flex items-center justify-center p-6 md:p-12">
        <motion.form
          onSubmit={handleSubmit}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-sm space-y-5"
        >
          <div>
            <h1 className="font-display text-2xl font-semibold text-ink">Welcome back</h1>
            <p className="mt-1 text-sm text-ink-muted">Sign in to continue to your account.</p>
          </div>

          <div>
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <Button type="submit" className="w-full" size="lg" isLoading={isLoggingIn}>
            Sign in
            <ArrowRight className="h-4 w-4" />
          </Button>

          <p className="text-center text-sm text-ink-muted">
            New here?{" "}
            <Link to="/register" className="text-accent-soft hover:underline">
              Create an account
            </Link>
          </p>
        </motion.form>
      </div>
    </div>
  );
}
