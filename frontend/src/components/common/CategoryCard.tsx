import { Link } from "react-router-dom";
import { Layers } from "lucide-react";
import type { Category } from "@/types";

export function CategoryCard({ category }: { category: Category }) {
  return (
    <Link
      to={`/category/${category.slug}`}
      className="bracket-frame group relative flex aspect-[4/3] flex-col justify-end overflow-hidden rounded-lg border border-border bg-bg-elevated p-5"
    >
      {category.image ? (
        <img
          src={category.image}
          alt=""
          className="absolute inset-0 h-full w-full object-cover opacity-60 transition-transform duration-500 group-hover:scale-105"
        />
      ) : (
        <Layers className="absolute right-4 top-4 h-16 w-16 text-white/[0.04]" strokeWidth={1} />
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/40 to-transparent" />
      <div className="relative">
        <h3 className="font-display text-lg font-semibold text-ink">{category.name}</h3>
        <p className="font-mono text-xs text-ink-muted">{category.product_count} 件商品</p>
      </div>
    </Link>
  );
}
