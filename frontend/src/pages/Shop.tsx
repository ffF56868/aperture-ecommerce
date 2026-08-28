import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PackageSearch, SlidersHorizontal } from "lucide-react";
import { productsApi } from "@/api/products";
import { Container } from "@/components/ui/Container";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { ProductCard } from "@/components/common/ProductCard";
import { EmptyState } from "@/components/common/EmptyState";
import { cn } from "@/utils/cn";

const SORT_OPTIONS = [
  { value: "", label: "推荐排序" },
  { value: "price", label: "价格从低到高" },
  { value: "-price", label: "价格从高到低" },
  { value: "-created_at", label: "最新上架" },
];

export function Shop() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filtersOpen, setFiltersOpen] = useState(false);

  const category = searchParams.get("category") ?? "";
  const popular = searchParams.get("popular") === "true";
  const search = searchParams.get("search") ?? "";
  const ordering = searchParams.get("ordering") ?? "";
  const maxPrice = searchParams.get("max_price") ?? "";

  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: productsApi.listCategories });
  const productsQuery = useQuery({
    queryKey: ["products", { category, popular, search, ordering, maxPrice }],
    queryFn: () =>
      productsApi.listProducts({
        category: category || undefined,
        popular: popular || undefined,
        search: search || undefined,
        ordering: ordering || undefined,
        max_price: maxPrice ? Number(maxPrice) : undefined,
      }),
  });

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  };

  const activeFilterCount = [category, popular ? "1" : "", maxPrice].filter(Boolean).length;

  return (
    <Container className="py-10">
      <div className="mb-8 flex flex-col gap-2">
        <h1 className="font-display text-3xl font-semibold text-ink">
          {search ? `“${search}” 的搜索结果` : "全部商品"}
        </h1>
        <p className="text-sm text-ink-muted">
          {productsQuery.data ? `共 ${productsQuery.data.count} 件商品` : "正在加载商品…"}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[220px_1fr]">
        {/* Filters sidebar */}
        <aside className={cn("space-y-6 lg:block", filtersOpen ? "block" : "hidden")}>
          <div>
            <h3 className="mb-3 font-mono text-xs uppercase tracking-wider text-ink-faint">商品分类</h3>
            <div className="flex flex-col gap-1">
              <button
                onClick={() => setParam("category", "")}
                className={cn(
                  "rounded-md px-2.5 py-1.5 text-left text-sm transition-colors",
                  !category ? "bg-accent/10 text-accent-soft" : "text-ink-muted hover:bg-white/[0.04]",
                )}
              >
                全部分类
              </button>
              {categoriesQuery.data?.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setParam("category", cat.slug)}
                  className={cn(
                    "rounded-md px-2.5 py-1.5 text-left text-sm transition-colors",
                    category === cat.slug
                      ? "bg-accent/10 text-accent-soft"
                      : "text-ink-muted hover:bg-white/[0.04]",
                  )}
                >
                  {cat.name}
                </button>
              ))}
            </div>
          </div>

          <div>
            <h3 className="mb-3 font-mono text-xs uppercase tracking-wider text-ink-faint">最高价格</h3>
            <input
              type="range"
              min={0}
              max={1000}
              step={10}
              value={maxPrice || 1000}
              onChange={(e) => setParam("max_price", e.target.value)}
              className="w-full accent-accent"
            />
            <div className="mt-1 font-mono text-xs text-ink-muted">
              {maxPrice ? `不超过 ￥${maxPrice}` : "不限价格"}
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm text-ink-muted">
            <input
              type="checkbox"
              checked={popular}
              onChange={(e) => setParam("popular", e.target.checked ? "true" : "")}
              className="accent-accent"
            />
            仅看热门商品
          </label>

          {activeFilterCount > 0 && (
            <Button variant="ghost" size="sm" onClick={() => setSearchParams({})}>
              清除筛选
            </Button>
          )}
        </aside>

        {/* Results */}
        <div>
          <div className="mb-5 flex items-center justify-between">
            <Button
              variant="secondary"
              size="sm"
              className="lg:hidden"
              onClick={() => setFiltersOpen((v) => !v)}
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              筛选 {activeFilterCount > 0 && `(${activeFilterCount})`}
            </Button>

            <select
              value={ordering}
              onChange={(e) => setParam("ordering", e.target.value)}
              className="ml-auto h-9 rounded-md border border-border-strong bg-bg-surface px-3 text-sm text-ink outline-none focus:border-accent"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {productsQuery.isLoading && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="aspect-square" />
              ))}
            </div>
          )}

          {productsQuery.data?.results.length === 0 && (
            <EmptyState
              icon={PackageSearch}
              title="没有符合条件的商品"
              description="请尝试放宽价格范围，或清除筛选条件后再试。"
              actionLabel="清除筛选"
              onAction={() => setSearchParams({})}
            />
          )}

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {productsQuery.data?.results.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </div>
      </div>
    </Container>
  );
}
