import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ImageOff, Minus, Plus, ShieldCheck, Truck } from "lucide-react";
import { productsApi } from "@/api/products";
import { Container } from "@/components/ui/Container";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatPrice } from "@/utils/format";
import { useCart } from "@/hooks/useCart";

export function ProductDetail() {
  const { slug } = useParams<{ slug: string }>();
  const [quantity, setQuantity] = useState(1);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const { addItem } = useCart();

  const { data: product, isLoading } = useQuery({
    queryKey: ["product", slug],
    queryFn: () => productsApi.getProduct(slug!),
    enabled: !!slug,
  });

  if (isLoading) {
    return (
      <Container className="py-10">
        <div className="grid gap-10 md:grid-cols-2">
          <Skeleton className="aspect-square" />
          <div className="space-y-4">
            <Skeleton className="h-6 w-1/3" />
            <Skeleton className="h-10 w-2/3" />
            <Skeleton className="h-24 w-full" />
          </div>
        </div>
      </Container>
    );
  }

  if (!product) {
    return (
      <Container className="py-24 text-center">
        <p className="text-ink-muted">Product not found.</p>
        <Link to="/products" className="mt-4 inline-block text-sm text-accent-soft hover:underline">
          Back to shop
        </Link>
      </Container>
    );
  }

  return (
    <Container className="py-10">
      <Link
        to="/products"
        className="mb-6 inline-flex items-center gap-1 text-sm text-ink-muted hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to shop
      </Link>

      <div className="grid gap-10 md:grid-cols-2">
        {/* Gallery */}
        <div>
          <button
            onClick={() => product.image && setLightboxOpen(true)}
            className="block w-full overflow-hidden rounded-lg border border-border bg-bg-elevated aspect-square"
          >
            {product.image ? (
              <img src={product.image} alt={product.name} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full w-full items-center justify-center">
                <ImageOff className="h-12 w-12 text-ink-faint" strokeWidth={1.25} />
              </div>
            )}
          </button>
        </div>

        {/* Info */}
        <div className="flex flex-col">
          <span className="font-mono text-xs uppercase tracking-wider text-accent-soft">
            {product.category?.name}
          </span>
          <h1 className="mt-1 font-display text-3xl font-semibold text-ink">{product.name}</h1>

          <div className="mt-3 flex items-center gap-2">
            <Badge variant={product.in_stock ? "success" : "danger"}>
              {product.in_stock ? "In stock" : "Out of stock"}
            </Badge>
            {product.is_featured && <Badge variant="coral">Featured</Badge>}
          </div>

          <p className="mt-5 font-mono text-3xl font-semibold text-ink">{formatPrice(product.price)}</p>

          {product.short_description && (
            <p className="mt-4 text-sm text-ink-muted">{product.short_description}</p>
          )}

          <div className="mt-8 flex items-center gap-4">
            <div className="flex items-center rounded-md border border-border-strong">
              <button
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                className="flex h-11 w-11 items-center justify-center text-ink-muted hover:text-ink"
                aria-label="Decrease quantity"
              >
                <Minus className="h-4 w-4" />
              </button>
              <span className="w-10 text-center font-mono text-sm">{quantity}</span>
              <button
                onClick={() => setQuantity((q) => q + 1)}
                className="flex h-11 w-11 items-center justify-center text-ink-muted hover:text-ink"
                aria-label="Increase quantity"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>

            <Button
              size="lg"
              className="flex-1"
              disabled={!product.in_stock}
              onClick={() => addItem(product, quantity)}
            >
              {product.in_stock ? "Add to cart" : "Out of stock"}
            </Button>
          </div>

          <div className="mt-8 flex flex-col gap-3 border-t border-border pt-6">
            <div className="flex items-center gap-2.5 text-sm text-ink-muted">
              <Truck className="h-4 w-4 text-accent-soft" />
              Estimated delivery: {product.delivery_estimate_days ?? 3} days
            </div>
            <div className="flex items-center gap-2.5 text-sm text-ink-muted">
              <ShieldCheck className="h-4 w-4 text-accent-soft" />
              Inspected and verified before dispatch
            </div>
          </div>

          {product.full_description && (
            <div className="mt-8 border-t border-border pt-6">
              <h2 className="mb-2 font-display text-sm font-semibold text-ink">Details</h2>
              <p className="whitespace-pre-line text-sm leading-relaxed text-ink-muted">
                {product.full_description}
              </p>
            </div>
          )}
        </div>
      </div>

      {lightboxOpen && product.image && (
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/85 p-6 backdrop-blur-sm"
          onClick={() => setLightboxOpen(false)}
        >
          <img
            src={product.image}
            alt={product.name}
            className="max-h-full max-w-full rounded-lg object-contain"
          />
        </div>
      )}
    </Container>
  );
}
