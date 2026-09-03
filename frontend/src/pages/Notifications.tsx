import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, CircleAlert, FileCheck2, Info, RotateCcw } from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";
import { afterSalesApi } from "@/api/afterSales";
import { getErrorMessage } from "@/api/client";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/hooks/useAuth";
import { toast } from "@/store/toastStore";
import type { AfterSalesNotification } from "@/types";
import { formatDateTime } from "@/utils/format";
import { cn } from "@/utils/cn";

function eventIcon(eventType: AfterSalesNotification["event_type"]) {
  if (eventType === "CASE_APPROVED") return FileCheck2;
  if (eventType === "CASE_REJECTED") return CircleAlert;
  if (eventType === "NEED_CUSTOMER_INFO") return RotateCcw;
  return Info;
}

export function Notifications() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const notificationsQuery = useQuery({
    queryKey: ["after-sales-notifications"],
    queryFn: afterSalesApi.listNotifications,
    enabled: isAuthenticated,
  });

  const readMutation = useMutation({
    mutationFn: afterSalesApi.markNotificationRead,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["after-sales-notifications"] });
    },
    onError: (error) => toast.error(getErrorMessage(error, "通知状态更新失败，请稍后重试。")),
  });

  const readAllMutation = useMutation({
    mutationFn: afterSalesApi.markAllNotificationsRead,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["after-sales-notifications"] });
      toast.success("通知已全部标记为已读。 ");
    },
    onError: (error) => toast.error(getErrorMessage(error, "通知状态更新失败，请稍后重试。")),
  });

  const notifications = useMemo(
    () => notificationsQuery.data?.notifications ?? [],
    [notificationsQuery.data?.notifications],
  );

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Container className="py-10 sm:py-12">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-md bg-accent/15 text-accent">
            <Bell className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-display text-3xl font-semibold text-ink">通知中心</h1>
            <p className="mt-1 text-sm text-ink-muted">
              {notificationsQuery.data?.unread_count ?? 0} 条未读通知
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => readAllMutation.mutate()}
          isLoading={readAllMutation.isPending}
          disabled={!notificationsQuery.data?.unread_count}
        >
          {!readAllMutation.isPending && <CheckCheck className="h-3.5 w-3.5" />}
          全部已读
        </Button>
      </div>

      {notificationsQuery.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
      ) : notificationsQuery.isError ? (
        <div className="border border-danger/30 bg-danger/5 p-5 text-sm text-danger">
          通知加载失败，请刷新页面后重试。
        </div>
      ) : notifications.length === 0 ? (
        <EmptyState icon={Bell} title="暂时没有通知" description="售后工单有新进展时，会显示在这里。" />
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-bg-surface">
          {notifications.map((notification) => {
            const Icon = eventIcon(notification.event_type);
            return (
              <li
                key={notification.id}
                className={cn(
                  "flex gap-4 p-5 transition-colors hover:bg-white/[0.03]",
                  !notification.is_read && "bg-accent/[0.04]",
                )}
              >
                <div
                  className={cn(
                    "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md",
                    notification.is_read ? "bg-white/[0.06] text-ink-muted" : "bg-accent/15 text-accent",
                  )}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => {
                    if (!notification.is_read) readMutation.mutate(notification.id);
                    navigate(notification.action_url || "/after-sales");
                  }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <h2 className="text-sm font-semibold text-ink">{notification.title}</h2>
                    <time className="shrink-0 text-xs text-ink-faint">
                      {formatDateTime(notification.created_at)}
                    </time>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-ink-muted">{notification.message}</p>
                  {notification.case_number && (
                    <p className="mt-2 font-mono text-xs text-accent">工单 {notification.case_number}</p>
                  )}
                </button>
                {!notification.is_read && (
                  <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-coral" aria-label="未读" />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Container>
  );
}
