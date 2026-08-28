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
import { ORDER_STATUS_LABEL } from "@/constants";
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
      setError(getErrorMessage(err, "订单提交失败，请稍后重试。"));
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
      setError(getErrorMessage(err, "支付处理失败，请稍后重试。"));
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
        <p className="font-display text-lg font-semibold text-ink">正在处理支付…</p>
        <p className="text-sm text-ink-muted">通常只需要几秒钟。</p>
      </Container>
    );
  }

  if (step === "success" && completedOrder) {
    return (
      <Container className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-success/10">
          <CheckCircle2 className="h-7 w-7 text-success" />
        </div>
        <h1 className="font-display text-2xl font-semibold text-ink">订单已确认</h1>
        <p className="max-w-sm text-sm text-ink-muted">
          订单 <span className="font-mono text-ink">#{completedOrder.id.slice(0, 8)}</span> 当前状态为{" "}
          <span className="text-success">{ORDER_STATUS_LABEL[completedOrder.status]}</span>，订单记录已保存至你的账户。
        </p>
        <p className="font-mono text-2xl font-semibold text-ink">
          {formatPrice(completedOrder.total_amount)}
        </p>
        <div className="mt-4 flex gap-3">
          <Button variant="secondary" onClick={() => navigate("/profile")}>
            查看订单记录
          </Button>
          <Button onClick={() => navigate("/products")}>继续选购</Button>
        </div>
      </Container>
    );
  }

  return (
    <Container className="py-10">
      <h1 className="mb-8 font-display text-3xl font-semibold text-ink">结算</h1>

      <div className="grid gap-10 lg:grid-cols-[1fr_340px]">
        <form onSubmit={handlePlaceOrder} className="space-y-5">
          {error && (
            <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <div>
            <Label htmlFor="address">收货地址</Label>
            <Input
              id="address"
              placeholder="例如：上海市浦东新区世纪大道 100 号"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              required
            />
          </div>

          <div className="rounded-lg border border-border-strong bg-bg-surface p-4">
            <div className="flex items-center gap-2 text-sm text-ink">
              <CreditCard className="h-4 w-4 text-accent-soft" />
              模拟支付
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              这是项目演示用的模拟支付流程，不会发生真实扣款。
            </p>
          </div>

          <Button type="submit" size="lg" className="w-full">
            提交订单 - {formatPrice(subtotal)}
          </Button>
        </form>

        <div className="h-fit rounded-lg border border-border bg-bg-surface p-5">
          <h2 className="font-display text-sm font-semibold text-ink">商品清单</h2>
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
            <span>合计</span>
            <span className="font-mono">{formatPrice(subtotal)}</span>
          </div>
        </div>
      </div>
    </Container>
  );
}
