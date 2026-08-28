import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { Aperture, Gauge, ShieldCheck, Sparkles } from "lucide-react";
import { Container } from "@/components/ui/Container";

const STATS = [
  { label: "累计发货商品", value: 128_400, suffix: "+" },
  { label: "退货率", value: 1.2, suffix: "%", decimals: 1 },
  { label: "平均评分", value: 4.9, suffix: "/5", decimals: 1 },
  { label: "服务地区", value: 34, suffix: "" },
];

const VALUES = [
  {
    icon: ShieldCheck,
    title: "发货前人工核验",
    body: "每一件商品都会由人工对照商品信息检查，而不是只依赖程序。",
  },
  {
    icon: Gauge,
    title: "只选值得的商品",
    body: "我们宁愿认真挑选 200 件放心的商品，也不愿堆砌两万件普通库存。",
  },
  {
    icon: Sparkles,
    title: "耐用，值得长期使用",
    body: "我们更青睐耐用、可维护的好物，而非一次性消耗品。",
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
            我们的故事
          </motion.div>
          <h1 className="mt-5 font-display text-4xl font-semibold leading-tight text-ink">
            我们创建聚焦好物，是因为多数商店只在意点击量，而不是商品本身。
          </h1>
          <p className="mt-5 text-base leading-relaxed text-ink-muted">
            聚焦好物起源于一份我们亲自使用、也愿意推荐给朋友的小清单。我们厌倦了信息含糊的商品页和避重就轻的图片，
            因此决定做一个自己愿意使用的商店：信息清楚、展示真实，并以真诚的售后服务对待每一位顾客。
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
          <h2 className="mb-8 font-display text-2xl font-semibold text-ink">我们坚持的标准</h2>
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
          <h2 className="mt-3 font-display text-xl font-semibold text-ink">聚焦好物保障</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">
            如果商品与页面描述不符，我们会在 30 天内为你安排退款或换货，由你选择。
          </p>
        </Container>
      </section>
    </div>
  );
}
