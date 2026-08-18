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
  { icon: Mail, title: "Email", value: "hello@aperture.shop" },
  { icon: Phone, title: "Phone", value: "+1 (415) 555-0134" },
  { icon: MapPin, title: "Studio", value: "San Francisco, CA" },
];

const HOURS = [
  ["Mon – Fri", "9:00am – 6:00pm PT"],
  ["Saturday", "10:00am – 4:00pm PT"],
  ["Sunday", "Closed"],
];

const initialForm = { full_name: "", email: "", phone_number: "", subject: "", message: "" };

export function Contact() {
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: contactApi.submit,
    onSuccess: () => {
      toast.success("Message sent — we'll reply within one business day.");
      setForm(initialForm);
    },
    onError: (err) => setError(getErrorMessage(err, "Could not send your message.")),
  });

  return (
    <Container className="py-16">
      <div className="mb-12 max-w-xl">
        <h1 className="font-display text-3xl font-semibold text-ink">Get in touch</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Questions about an order, a product, or a partnership — we read everything.
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
              <Label htmlFor="full_name">Full name</Label>
              <Input
                id="full_name"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
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
            <Label htmlFor="subject">Subject</Label>
            <Input
              id="subject"
              value={form.subject}
              onChange={(e) => setForm({ ...form, subject: e.target.value })}
              required
            />
          </div>

          <div>
            <Label htmlFor="message">Message</Label>
            <Textarea
              id="message"
              value={form.message}
              onChange={(e) => setForm({ ...form, message: e.target.value })}
              required
            />
          </div>

          <Button type="submit" size="lg" isLoading={mutation.isPending}>
            Send message
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
              Hours
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
              <p className="mt-1 text-xs">Map view placeholder</p>
            </div>
          </div>
        </div>
      </div>
    </Container>
  );
}
