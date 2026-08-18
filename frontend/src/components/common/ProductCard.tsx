import { Link } from "react-router-dom";
import { ImageOff, Plus } from "lucide-react";
import type { Product } from "@/types";
import { formatPrice } from "@/utils/format";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useCart } from "@/hooks/useCart";

export function ProductCard({ product }: { product: Product }) {
  const { addItem } = useCart();

  return (
    <div className="bracket-frame group flex flex-col overflow-hidden rounded-lg border border-border bg-bg-surface transition-colors hover:border-border-strong">
      <Link
        to={`/product/${product.slug}`}
        className="relative block aspect-square overflow-hidden bg-bg-elevated"
      >
        {product.image ? (
          <img
            src={product.image}
            alt={product.name}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ImageOff className="h-8 w-8 text-ink-faint" strokeWidth={1.25} />
          </div>
        )}

        {product.is_featured && (
          <Badge variant="coral" className="absolute left-3 top-3">
            Featured
          </Badge>
        )}
        {!product.in_stock && (
          <Badge variant="danger" className="absolute right-3 top-3">
            Out of stock
          </Badge>
        )}
      </Link>

      <div className="flex flex-1 flex-col gap-1 p-4">
        <span className="font-mono text-[11px] uppercase tracking-wider text-ink-faint">
          {product.category_name}
        </span>
        <Link
          to={`/product/${product.slug}`}
          className="line-clamp-1 font-display text-sm font-semibold text-ink hover:text-accent-soft transition-colors"
        >
          {product.name}
        </Link>
        {product.short_description && (
          <p className="line-clamp-2 text-xs text-ink-muted">{product.short_description}</p>
        )}

        <div className="mt-3 flex items-center justify-between">
          <span className="font-mono text-base font-semibold text-ink">{formatPrice(product.price)}</span>
          <Button
            size="sm"
            variant="secondary"
            disabled={!product.in_stock}
            onClick={(e) => {
              e.preventDefault();
              addItem(product, 1);
            }}
            aria-label={`Add ${product.name} to cart`}
          >
            <Plus className="h-3.5 w-3.5" />
            Add
          </Button>
        </div>
      </div>
    </div>
  );
}
