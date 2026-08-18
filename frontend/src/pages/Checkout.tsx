import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CreditCard, Loader2 } from "lucide-react";
import { ordersApi, paymentsApi } from "@/api/cartOrders";
import { getErrorMessage } from "@/api/client";
import { Container } from "@/components/ui/Container";
import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Input";
import { useCart } from "@/hooks/useCart";
import { formatPrice } from "@/utils/format";
import type { Order } from "@/types";

type Step = "details" | "processing" | "success";

export function Checkout() {
  const { items, subtotal, clear } = useCart();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<Step>("details");
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [completedOrder, setCompletedOrder] = useState<Order | null>(null);

  const checkoutMutation = useMutation({
    mutationFn: () => ordersApi.checkout({ shipping_address: address, tax_rate: "0.080" }),
    onError: (err) => {
      setError(getErrorMessage(err, "Could not place your order."));
      setStep("details");
    },
  });

  const handlePlaceOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setStep("processing");

    try {
      const order = await checkoutMutation.mutateAsync();
      const { transaction_id } = await paymentsApi.initiate(order.id);
      const { order_status } = await paymentsApi.verify(transaction_id, true);

      setCompletedOrder({ ...order, status: order_status as Order["status"] });
      queryClient.invalidateQueries({ queryKey: ["cart"] });
      clear();
      setStep("success");
    } catch (err) {
      setError(getErrorMessage(err, "Payment could not be processed."));
      setStep("details");
    }
  };

  if (items.length === 0 && step === "details") {
    navigate("/cart");
    return null;
  }

  if (step === "processing") {
    return (
      <Container className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-accent" />
        <p className="font-display text-lg font-semibold text-ink">Processing your payment…</p>
        <p className="text-sm text-ink-muted">This usually takes a few seconds.</p>
      </Container>
    );
  }

  if (step === "success" && completedOrder) {
    return (
      <Container className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-success/10">
          <CheckCircle2 className="h-7 w-7 text-success" />
        </div>
        <h1 className="font-display text-2xl font-semibold text-ink">Order confirmed</h1>
        <p className="max-w-sm text-sm text-ink-muted">
          Order <span className="font-mono text-ink">#{completedOrder.id.slice(0, 8)}</span> is{" "}
          <span className="text-success">{completedOrder.status.toLowerCase()}</span>. A receipt has been
          recorded to your account.
        </p>
        <p className="font-mono text-2xl font-semibold text-ink">
          {formatPrice(completedOrder.total_amount)}
        </p>
        <div className="mt-4 flex gap-3">
          <Button variant="secondary" onClick={() => navigate("/profile")}>
            View order history
          </Button>
          <Button onClick={() => navigate("/products")}>Continue shopping</Button>
        </div>
      </Container>
    );
  }

  return (
    <Container className="py-10">
      <h1 className="mb-8 font-display text-3xl font-semibold text-ink">Checkout</h1>

      <div className="grid gap-10 lg:grid-cols-[1fr_340px]">
        <form onSubmit={handlePlaceOrder} className="space-y-5">
          {error && (
            <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <div>
            <Label htmlFor="address">Shipping address</Label>
            <Input
              id="address"
              placeholder="123 Main St, San Francisco, CA 94103"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              required
            />
          </div>

          <div className="rounded-lg border border-border-strong bg-bg-surface p-4">
            <div className="flex items-center gap-2 text-sm text-ink">
              <CreditCard className="h-4 w-4 text-accent-soft" />
              Mock payment gateway
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              This is a simulated payment flow for demonstration — no real charge occurs.
            </p>
          </div>

          <Button type="submit" size="lg" className="w-full">
            Place order — {formatPrice(subtotal)}
          </Button>
        </form>

        <div className="h-fit rounded-lg border border-border bg-bg-surface p-5">
          <h2 className="font-display text-sm font-semibold text-ink">Items</h2>
          <ul className="mt-3 space-y-2">
            {items.map((item) => (
              <li key={item.id} className="flex justify-between text-sm text-ink-muted">
                <span>
                  {item.quantity} &times; {item.product_name}
                </span>
                <span className="font-mono text-ink">{formatPrice(item.line_total)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex justify-between border-t border-border pt-4 text-base font-semibold text-ink">
            <span>Total</span>
            <span className="font-mono">{formatPrice(subtotal)}</span>
          </div>
        </div>
      </div>
    </Container>
  );
}
