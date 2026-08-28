import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Clock, Mail, MapPin, Phone, Send } from "lucide-react";
import { contactApi } from "@/api/contact";
import { getErrorMessage } from "@/api/client";
import { Container } from "@/components/ui/Container";
import { Button } from "@/components/ui/Button";
import { Input, Label, Textarea } from "@/components/ui/Input";
import { toast } from "@/store/toastStore";

const CARDS = [
  { icon: Mail, title: "邮箱", value: "hello@aperture.shop" },
  { icon: Phone, title: "电话", value: "+86 400-555-0134" },
  { icon: MapPin, title: "工作室", value: "上海市" },
];

const HOURS = [
  ["周一至周五", "09:00 - 18:00"],
  ["周六", "10:00 - 16:00"],
  ["周日", "休息"],
];

const initialForm = { full_name: "", email: "", phone_number: "", subject: "", message: "" };

export function Contact() {
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: contactApi.submit,
    onSuccess: () => {
      toast.success("消息已发送，我们会在一个工作日内回复。 ");
      setForm(initialForm);
    },
    onError: (err) => setError(getErrorMessage(err, "消息发送失败，请稍后重试。")),
  });

  return (
    <Container className="py-16">
      <div className="mb-12 max-w-xl">
        <h1 className="font-display text-3xl font-semibold text-ink">联系我们</h1>
        <p className="mt-2 text-sm text-ink-muted">
          关于订单、商品或合作的任何问题，都欢迎告诉我们。
        </p>
      </div>

      <div className="grid gap-10 lg:grid-cols-[1fr_380px]">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            mutation.mutate(form);
          }}
          className="space-y-4"
        >
          {error && (
            <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="full_name">姓名</Label>
              <Input
                id="full_name"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="email">邮箱</Label>
              <Input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>
          </div>

          <div>
            <Label htmlFor="subject">主题</Label>
            <Input
              id="subject"
              value={form.subject}
              onChange={(e) => setForm({ ...form, subject: e.target.value })}
              required
            />
          </div>

          <div>
            <Label htmlFor="message">留言内容</Label>
            <Textarea
              id="message"
              value={form.message}
              onChange={(e) => setForm({ ...form, message: e.target.value })}
              required
            />
          </div>

          <Button type="submit" size="lg" isLoading={mutation.isPending}>
            发送留言
            <Send className="h-4 w-4" />
          </Button>
        </form>

        <div className="space-y-6">
          <div className="grid gap-3">
            {CARDS.map((card) => (
              <div
                key={card.title}
                className="flex items-center gap-3 rounded-lg border border-border bg-bg-surface p-4"
              >
                <card.icon className="h-4.5 w-4.5 text-accent-soft" />
                <div>
                  <p className="text-xs text-ink-faint">{card.title}</p>
                  <p className="text-sm text-ink">{card.value}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-border bg-bg-surface p-4">
            <div className="mb-2 flex items-center gap-2 text-sm text-ink">
              <Clock className="h-4 w-4 text-accent-soft" />
              服务时间
            </div>
            <ul className="space-y-1">
              {HOURS.map(([day, time]) => (
                <li key={day} className="flex justify-between text-xs text-ink-muted">
                  <span>{day}</span>
                  <span className="font-mono">{time}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-border-strong bg-bg-elevated">
            <div className="text-center text-ink-faint">
              <MapPin className="mx-auto h-6 w-6" strokeWidth={1.25} />
              <p className="mt-1 text-xs">地图位置</p>
            </div>
          </div>
        </div>
      </div>
    </Container>
  );
}
