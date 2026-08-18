import { Link, useNavigate } from "react-router-dom";
import { ImageOff, Minus, Plus, ShoppingBag, Trash2 } from "lucide-react";
import { Container } from "@/components/ui/Container";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/common/EmptyState";
import { useCart } from "@/hooks/useCart";
import { formatPrice } from "@/utils/format";

export function CartPage() {
  const { items, subtotal, updateQuantity, removeItem, isLoading, isAuthenticated } = useCart();
  const navigate = useNavigate();

  if (isLoading) {
    return <Container className="py-16 text-center text-sm text-ink-muted">Loading your cart…</Container>;
  }

  if (items.length === 0) {
    return (
      <Container className="py-16">
        <EmptyState
          icon={ShoppingBag}
          title="Your cart is empty"
          description="Browse the catalog and add something worth focusing on."
          actionLabel="Shop products"
          onAction={() => navigate("/products")}
        />
      </Container>
    );
  }

  return (
    <Container className="py-10">
      <h1 className="mb-8 font-display text-3xl font-semibold text-ink">Your cart</h1>

      <div className="grid gap-10 lg:grid-cols-[1fr_340px]">
        <ul className="divide-y divide-border rounded-lg border border-border">
          {items.map((item) => (
            <li key={item.id} className="flex gap-4 p-4">
              <div className="h-20 w-20 shrink-0 overflow-hidden rounded-md bg-bg-elevated">
                {item.product_image ? (
                  <img src={item.product_image} alt="" className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center">
                    <ImageOff className="h-5 w-5 text-ink-faint" />
                  </div>
                )}
              </div>

              <div className="flex flex-1 flex-col justify-between">
                <div className="flex items-start justify-between gap-2">
                  <Link
                    to={`/product/${item.product_slug}`}
                    className="font-display text-sm font-semibold text-ink hover:text-accent-soft"
                  >
                    {item.product_name}
                  </Link>
                  <button
                    onClick={() => removeItem(item.id)}
                    className="text-ink-faint hover:text-danger"
                    aria-label="Remove item"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center rounded-md border border-border-strong">
                    <button
                      onClick={() => updateQuantity(item.id, Math.max(1, item.quantity - 1))}
                      className="flex h-8 w-8 items-center justify-center text-ink-muted hover:text-ink"
                      aria-label="Decrease quantity"
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </button>
                    <span className="w-8 text-center font-mono text-xs">{item.quantity}</span>
                    <button
                      onClick={() => updateQuantity(item.id, item.quantity + 1)}
                      className="flex h-8 w-8 items-center justify-center text-ink-muted hover:text-ink"
                      aria-label="Increase quantity"
                    >
                      <Plus className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <span className="font-mono text-sm font-semibold text-ink">
                    {formatPrice(item.line_total)}
                  </span>
                </div>
              </div>
            </li>
          ))}
        </ul>

        <div className="h-fit rounded-lg border border-border bg-bg-surface p-5">
          <h2 className="font-display text-sm font-semibold text-ink">Order summary</h2>
          <div className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between text-ink-muted">
              <span>Subtotal</span>
              <span className="font-mono text-ink">{formatPrice(subtotal)}</span>
            </div>
            <div className="flex justify-between text-ink-muted">
              <span>Shipping &amp; tax</span>
              <span className="font-mono">Calculated at checkout</span>
            </div>
          </div>
          <div className="mt-4 flex justify-between border-t border-border pt-4 text-base font-semibold text-ink">
            <span>Total</span>
            <span className="font-mono">{formatPrice(subtotal)}</span>
          </div>

          <Button
            className="mt-5 w-full"
            size="lg"
            onClick={() => navigate(isAuthenticated ? "/checkout" : "/login")}
          >
            {isAuthenticated ? "Proceed to checkout" : "Sign in to checkout"}
          </Button>
          {!isAuthenticated && (
            <p className="mt-2 text-center text-xs text-ink-faint">
              Your cart is saved locally and will merge into your account once you sign in.
            </p>
          )}
        </div>
      </div>
    </Container>
  );
}
