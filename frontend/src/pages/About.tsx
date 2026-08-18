import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { Aperture, Gauge, ShieldCheck, Sparkles } from "lucide-react";
import { Container } from "@/components/ui/Container";

const STATS = [
  { label: "Items shipped", value: 128_400, suffix: "+" },
  { label: "Return rate", value: 1.2, suffix: "%", decimals: 1 },
  { label: "Avg. rating", value: 4.9, suffix: "/5", decimals: 1 },
  { label: "Countries served", value: 34, suffix: "" },
];

const VALUES = [
  {
    icon: ShieldCheck,
    title: "Verified before it ships",
    body: "Every listing is checked against its spec sheet by a human, not just a script.",
  },
  {
    icon: Gauge,
    title: "No filler inventory",
    body: "We'd rather stock 200 things we trust than 20,000 things we don't.",
  },
  {
    icon: Sparkles,
    title: "Made to be kept",
    body: "We favor durable, repairable goods over disposable ones.",
  },
];

function useCountUp(target: number, decimals = 0, active: boolean) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!active) return;
    let frame: number;
    const duration = 1200;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(target * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [active, target]);
  return value.toFixed(decimals);
}

function StatCounter({ value, decimals = 0, suffix, label }: (typeof STATS)[number]) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const display = useCountUp(value, decimals, inView);

  return (
    <div ref={ref}>
      <p className="font-mono text-3xl font-semibold text-ink">
        {display}
        {suffix}
      </p>
      <p className="mt-1 text-sm text-ink-muted">{label}</p>
    </div>
  );
}

export function About() {
  return (
    <div>
      <section className="border-b border-border py-20">
        <Container className="max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 rounded-full border border-border-strong bg-white/[0.03] px-3 py-1 font-mono text-xs text-ink-muted"
          >
            <Aperture className="h-3.5 w-3.5 text-accent" />
            Our story
          </motion.div>
          <h1 className="mt-5 font-display text-4xl font-semibold leading-tight text-ink">
            We started Aperture because most stores optimize for the click, not the object.
          </h1>
          <p className="mt-5 text-base leading-relaxed text-ink-muted">
            Aperture began as a small catalog of tools we personally used and trusted. We were tired of
            product pages that told us nothing and photos that hid more than they showed. So we built the
            store we wished existed: precise specs, honest photography, and a return policy that assumes good
            faith.
          </p>
        </Container>
      </section>

      <section className="border-b border-border py-16">
        <Container className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          {STATS.map((stat) => (
            <StatCounter key={stat.label} {...stat} />
          ))}
        </Container>
      </section>

      <section className="py-16">
        <Container>
          <h2 className="mb-8 font-display text-2xl font-semibold text-ink">What we hold ourselves to</h2>
          <div className="grid gap-8 sm:grid-cols-3">
            {VALUES.map((v) => (
              <div key={v.title} className="flex flex-col gap-3">
                <v.icon className="h-5 w-5 text-accent" strokeWidth={1.75} />
                <h3 className="font-display text-base font-semibold text-ink">{v.title}</h3>
                <p className="text-sm text-ink-muted">{v.body}</p>
              </div>
            ))}
          </div>
        </Container>
      </section>

      <section className="border-t border-border py-16">
        <Container className="rounded-lg border border-accent/20 bg-accent/5 p-8 text-center">
          <ShieldCheck className="mx-auto h-8 w-8 text-accent" />
          <h2 className="mt-3 font-display text-xl font-semibold text-ink">The Aperture Guarantee</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">
            If an item doesn't match its listing, we'll make it right — full refund or replacement, your call,
            within 30 days.
          </p>
        </Container>
      </section>
    </div>
  );
}
