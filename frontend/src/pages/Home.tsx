import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, Aperture, ShieldCheck, Truck, Undo2 } from "lucide-react";
import { productsApi } from "@/api/products";
import { Container } from "@/components/ui/Container";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ProductCard } from "@/components/common/ProductCard";
import { CategoryCard } from "@/components/common/CategoryCard";

const VALUES = [
  {
    icon: ShieldCheck,
    title: "品质核验",
    body: "每件商品发货前都会按标准逐一检查。",
  },
  { icon: Truck, title: "快速发货", body: "下午三点前完成的订单，当天交给承运方。" },
  { icon: Undo2, title: "30 天退换", body: "不合适可以退回，无需繁琐解释。" },
];

export function Home() {
  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: productsApi.listCategories });
  const featuredQuery = useQuery({
    queryKey: ["products", { popular: true }],
    queryFn: () => productsApi.listProducts({ popular: true }),
  });

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
        <Container className="relative flex flex-col items-start gap-6 py-24 md:py-32">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="inline-flex items-center gap-2 rounded-full border border-border-strong bg-white/[0.03] px-3 py-1 font-mono text-xs text-ink-muted"
          >
            <Aperture className="h-3.5 w-3.5 text-accent" />
            f/1.0 - 为细节而生
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
            className="max-w-2xl font-display text-4xl font-semibold leading-[1.05] tracking-tight text-ink sm:text-5xl md:text-6xl"
          >
            每一件好物，
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent to-coral">
              都清晰可见。
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            className="max-w-lg text-base text-ink-muted"
          >
            聚焦好物为在意品质的人挑选可靠的工具与生活好物，提供清晰信息、真实展示与安心配送。
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          >
            <Link to="/products">
              <Button size="lg">
                浏览商品
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </motion.div>
        </Container>
      </section>

      {/* Categories */}
      <section className="py-16">
        <Container>
          <div className="mb-6 flex items-end justify-between">
            <h2 className="font-display text-2xl font-semibold text-ink">按分类选购</h2>
            <Link to="/products" className="text-sm text-ink-muted hover:text-ink">
              查看全部
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {categoriesQuery.isLoading &&
              Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="aspect-[4/3]" />)}
            {categoriesQuery.data?.slice(0, 4).map((cat) => (
              <CategoryCard key={cat.id} category={cat} />
            ))}
          </div>
        </Container>
      </section>

      {/* Featured products */}
      <section className="border-t border-border py-16">
        <Container>
          <div className="mb-6 flex items-end justify-between">
            <h2 className="font-display text-2xl font-semibold text-ink">热门推荐</h2>
            <Link to="/products?popular=true" className="text-sm text-ink-muted hover:text-ink">
              查看全部
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {featuredQuery.isLoading &&
              Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="aspect-square" />)}
            {featuredQuery.data?.results.slice(0, 8).map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
            {featuredQuery.data?.results.length === 0 && (
              <p className="col-span-full py-8 text-center text-sm text-ink-muted">
                暂无推荐商品，稍后再来看看。
              </p>
            )}
          </div>
        </Container>
      </section>

      {/* Brand values */}
      <section className="border-t border-border py-16">
        <Container className="grid gap-8 sm:grid-cols-3">
          {VALUES.map((v) => (
            <div key={v.title} className="flex flex-col gap-3">
              <v.icon className="h-5 w-5 text-accent" strokeWidth={1.75} />
              <h3 className="font-display text-base font-semibold text-ink">{v.title}</h3>
              <p className="text-sm text-ink-muted">{v.body}</p>
            </div>
          ))}
        </Container>
      </section>
    </div>
  );
}
