import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useMutation } from "@tanstack/react-query";
import { Aperture, ArrowRight } from "lucide-react";
import { authApi } from "@/api/auth";
import { getErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Input";
import { toast } from "@/store/toastStore";

export function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", phone_number: "", password: "" });
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: authApi.register,
    onSuccess: () => {
      toast.success("验证码已发送，请查看手机。 ");
      navigate("/verify-otp", { state: { phoneNumber: form.phone_number } });
    },
    onError: (err) => setError(getErrorMessage(err, "账户创建失败，请稍后重试。")),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    mutation.mutate(form);
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
            加入一个为重视商品细节的人准备的好物目录。
          </p>
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
            <h1 className="font-display text-2xl font-semibold text-ink">创建账户</h1>
            <p className="mt-1 text-sm text-ink-muted">第 1 步，共 2 步：我们会向你的手机发送验证码。</p>
          </div>

          {error && (
            <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <div>
            <Label htmlFor="username">用户名</Label>
            <Input
              id="username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              required
            />
          </div>

          <div>
            <Label htmlFor="phone">手机号码</Label>
            <Input
              id="phone"
              type="tel"
              placeholder="+14155552671"
              value={form.phone_number}
              onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
              required
            />
            <p className="mt-1 text-xs text-ink-faint">使用国际号码格式，例如 +8613812345678</p>
          </div>

          <div>
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
              minLength={8}
            />
          </div>

          <Button type="submit" className="w-full" size="lg" isLoading={mutation.isPending}>
            发送验证码
            <ArrowRight className="h-4 w-4" />
          </Button>

          <p className="text-center text-sm text-ink-muted">
            已有账户？{" "}
            <Link to="/login" className="text-accent-soft hover:underline">
              去登录
            </Link>
          </p>
        </motion.form>
      </div>
    </div>
  );
}
