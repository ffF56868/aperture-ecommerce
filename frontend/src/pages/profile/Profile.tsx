import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { PackageOpen, LogOut } from "lucide-react";
import { authApi } from "@/api/auth";
import { ordersApi } from "@/api/cartOrders";
import { getErrorMessage } from "@/api/client";
import { Container } from "@/components/ui/Container";
import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { useAuth } from "@/hooks/useAuth";
import { useAuthStore } from "@/store/authStore";
import { toast } from "@/store/toastStore";
import { formatDate, formatPrice } from "@/utils/format";
import { ORDER_STATUS_COLOR, ORDER_STATUS_LABEL } from "@/constants";
import { cn } from "@/utils/cn";

type Tab = "orders" | "account";

export function Profile() {
  const [tab, setTab] = useState<Tab>("orders");
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) {
    navigate("/login");
    return null;
  }

  return (
    <Container className="py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-ink">Account</h1>
          <p className="mt-1 text-sm text-ink-muted">Signed in as {user.username}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => logout()}>
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </Button>
      </div>

      <div className="mb-6 flex gap-1 border-b border-border">
        {(["orders", "account"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
              tab === t ? "border-accent text-ink" : "border-transparent text-ink-muted hover:text-ink",
            )}
          >
            {t === "orders" ? "Order history" : "Account details"}
          </button>
        ))}
      </div>

      {tab === "orders" ? <OrderHistoryTab /> : <AccountDetailsTab />}
    </Container>
  );
}

function OrderHistoryTab() {
  const { data, isLoading } = useQuery({ queryKey: ["orders"], queryFn: ordersApi.listOrders });

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  }

  if (!data || data.results.length === 0) {
    return (
      <EmptyState
        icon={PackageOpen}
        title="No orders yet"
        description="Once you place an order, it'll show up here with its status."
      />
    );
  }

  return (
    <ul className="space-y-3">
      {data.results.map((order) => (
        <li key={order.id} className="rounded-lg border border-border bg-bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="font-mono text-xs text-ink-faint">#{order.id.slice(0, 8)}</span>
              <p className="text-sm text-ink-muted">{formatDate(order.created_at)}</p>
            </div>
            <div className="flex items-center gap-3">
              <Badge className={ORDER_STATUS_COLOR[order.status]}>{ORDER_STATUS_LABEL[order.status]}</Badge>
              <span className="font-mono text-sm font-semibold text-ink">
                {formatPrice(order.total_amount)}
              </span>
            </div>
          </div>
          <ul className="mt-3 space-y-1 border-t border-border pt-3">
            {order.items.map((item) => (
              <li key={item.id} className="flex justify-between text-xs text-ink-muted">
                <span>
                  {item.quantity} &times; {item.product_name}
                </span>
                <span className="font-mono">{formatPrice(item.line_total)}</span>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}

function AccountDetailsTab() {
  const { user, setUser } = useAuthStore();
  const [username, setUsername] = useState(user?.username ?? "");
  const [passwords, setPasswords] = useState({ current_password: "", new_password: "" });

  const usernameMutation = useMutation({
    mutationFn: authApi.changeUsername,
    onSuccess: (updated) => {
      setUser(updated);
      toast.success("Username updated.");
    },
    onError: (err) => toast.error(getErrorMessage(err, "Could not update username.")),
  });

  const passwordMutation = useMutation({
    mutationFn: authApi.changePassword,
    onSuccess: () => {
      toast.success("Password updated.");
      setPasswords({ current_password: "", new_password: "" });
    },
    onError: (err) => toast.error(getErrorMessage(err, "Could not update password.")),
  });

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          usernameMutation.mutate(username);
        }}
        className="space-y-4 rounded-lg border border-border bg-bg-surface p-5"
      >
        <h2 className="font-display text-sm font-semibold text-ink">Username</h2>
        <div>
          <Label htmlFor="username">Username</Label>
          <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div>
          <Label>Phone number</Label>
          <Input value={user?.phone_number ?? ""} disabled />
        </div>
        <Button type="submit" size="sm" isLoading={usernameMutation.isPending}>
          Save changes
        </Button>
      </form>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          passwordMutation.mutate(passwords);
        }}
        className="space-y-4 rounded-lg border border-border bg-bg-surface p-5"
      >
        <h2 className="font-display text-sm font-semibold text-ink">Password</h2>
        <div>
          <Label htmlFor="current_password">Current password</Label>
          <Input
            id="current_password"
            type="password"
            value={passwords.current_password}
            onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })}
            required
          />
        </div>
        <div>
          <Label htmlFor="new_password">New password</Label>
          <Input
            id="new_password"
            type="password"
            minLength={8}
            value={passwords.new_password}
            onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })}
            required
          />
        </div>
        <Button type="submit" size="sm" isLoading={passwordMutation.isPending}>
          Update password
        </Button>
      </form>
    </div>
  );
}
