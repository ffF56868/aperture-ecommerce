import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  ClipboardList,
  FileText,
  Loader2,
  Package,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Truck,
  UserRound,
} from "lucide-react";
import { Navigate } from "react-router-dom";
import { afterSalesApi } from "@/api/afterSales";
import { getErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { ORDER_STATUS_LABEL } from "@/constants";
import { useAuth } from "@/hooks/useAuth";
import { toast } from "@/store/toastStore";
import type { AfterSalesCaseStatus, OrderStatus, StaffAfterSalesCase, StaffOrder } from "@/types";
import { cn } from "@/utils/cn";
import { formatDateTime, formatPrice } from "@/utils/format";

const STATUS_OPTIONS: Array<{ value: AfterSalesCaseStatus; label: string }> = [
  { value: "PENDING_REVIEW", label: "待人工审核" },
  { value: "IN_REVIEW", label: "审核中" },
  { value: "NEED_CUSTOMER_INFO", label: "待用户补充" },
  { value: "APPROVED", label: "已通过" },
  { value: "REJECTED", label: "已拒绝" },
  { value: "CLOSED", label: "已关闭" },
  { value: "CANCELLED", label: "用户取消" },
];

const PRIORITY_OPTIONS = [
  { value: "LOW", label: "低优先级" },
  { value: "NORMAL", label: "普通优先级" },
  { value: "HIGH", label: "高优先级" },
  { value: "URGENT", label: "紧急" },
];

const ORDER_STATUS_OPTIONS: Array<{ value: OrderStatus; label: string }> = [
  { value: "PENDING", label: "待支付" },
  { value: "PAID", label: "已支付" },
  { value: "SHIPPED", label: "已发货" },
  { value: "CANCELLED", label: "已取消" },
  { value: "REFUNDED", label: "已退款" },
];

const STAFF_STATUS_TRANSITIONS: Record<AfterSalesCaseStatus, AfterSalesCaseStatus[]> = {
  PENDING_REVIEW: ["PENDING_REVIEW", "IN_REVIEW", "NEED_CUSTOMER_INFO", "APPROVED", "REJECTED", "CLOSED"],
  IN_REVIEW: ["IN_REVIEW", "NEED_CUSTOMER_INFO", "APPROVED", "REJECTED", "CLOSED"],
  NEED_CUSTOMER_INFO: ["NEED_CUSTOMER_INFO", "IN_REVIEW", "APPROVED", "REJECTED", "CLOSED"],
  APPROVED: ["APPROVED", "CLOSED"],
  REJECTED: ["REJECTED", "CLOSED"],
  CLOSED: ["CLOSED"],
  CANCELLED: ["CANCELLED"],
};

function priorityVariant(priority: StaffAfterSalesCase["priority"]): "default" | "accent" | "coral" | "danger" {
  if (priority === "URGENT") return "danger";
  if (priority === "HIGH") return "coral";
  if (priority === "LOW") return "default";
  return "accent";
}

function priorityLabel(priority: StaffAfterSalesCase["priority"]): string {
  return PRIORITY_OPTIONS.find((option) => option.value === priority)?.label ?? priority;
}

function orderStatusVariant(status: OrderStatus): "default" | "accent" | "coral" | "success" | "danger" {
  if (status === "SHIPPED") return "accent";
  if (status === "PAID") return "success";
  if (status === "REFUNDED") return "success";
  if (status === "CANCELLED") return "danger";
  return "coral";
}

export function StaffAfterSalesWorkbench() {
  const { isAuthenticated, user } = useAuth();
  const queryClient = useQueryClient();
  const [activeView, setActiveView] = useState<"cases" | "orders">("cases");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<AfterSalesCaseStatus>("PENDING_REVIEW");
  const [staffNote, setStaffNote] = useState("");
  const loadedCaseIdRef = useRef<string | null>(null);
  const [orderStatusFilter, setOrderStatusFilter] = useState("");
  const [orderSearchDraft, setOrderSearchDraft] = useState("");
  const [orderSearch, setOrderSearch] = useState("");
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(priorityFilter ? { priority: priorityFilter } : {}),
      ...(search ? { search } : {}),
    }),
    [priorityFilter, search, statusFilter],
  );

  const orderFilters = useMemo(
    () => ({
      ...(orderStatusFilter ? { status: orderStatusFilter } : {}),
      ...(orderSearch ? { search: orderSearch } : {}),
    }),
    [orderSearch, orderStatusFilter],
  );

  const casesQuery = useQuery({
    queryKey: ["staff-after-sales-cases", filters],
    queryFn: () => afterSalesApi.listStaffCases(filters),
    enabled: isAuthenticated && Boolean(user?.is_staff),
    refetchInterval: 30_000,
  });

  const selectedCaseQuery = useQuery({
    queryKey: ["staff-after-sales-case", selectedCaseId],
    queryFn: () => afterSalesApi.getStaffCase(selectedCaseId!),
    enabled: Boolean(selectedCaseId) && isAuthenticated && Boolean(user?.is_staff),
    refetchInterval: 30_000,
  });

  const ordersQuery = useQuery({
    queryKey: ["staff-orders", orderFilters],
    queryFn: () => afterSalesApi.listStaffOrders(orderFilters),
    enabled: isAuthenticated && Boolean(user?.is_staff) && activeView === "orders",
    refetchInterval: 30_000,
  });

  useEffect(() => {
    if (activeView !== "cases") return;
    const cases = casesQuery.data;
    if (!cases?.length) {
      setSelectedCaseId(null);
      return;
    }
    if (!selectedCaseId || !cases.some((afterSalesCase) => afterSalesCase.id === selectedCaseId)) {
      setSelectedCaseId(cases[0].id);
    }
  }, [activeView, casesQuery.data, selectedCaseId]);

  useEffect(() => {
    const selectedCase = selectedCaseQuery.data;
    if (!selectedCase || loadedCaseIdRef.current === selectedCase.id) return;

    loadedCaseIdRef.current = selectedCase.id;
    setSelectedStatus(selectedCase.status);
    setStaffNote(selectedCase.staff_note);
  }, [selectedCaseQuery.data]);

  useEffect(() => {
    if (activeView !== "orders") return;
    const orders = ordersQuery.data;
    if (!orders?.length) {
      setSelectedOrderId(null);
      return;
    }
    if (!selectedOrderId || !orders.some((order) => order.id === selectedOrderId)) {
      setSelectedOrderId(orders[0].id);
    }
  }, [activeView, ordersQuery.data, selectedOrderId]);

  const updateMutation = useMutation({
    mutationFn: (payload: { caseId: string; status: AfterSalesCaseStatus; staffNote: string }) =>
      afterSalesApi.updateStaffCase(payload.caseId, {
        status: payload.status,
        staff_note: payload.staffNote,
      }),
    onSuccess: (updatedCase) => {
      queryClient.setQueryData(["staff-after-sales-case", updatedCase.id], updatedCase);
      setSelectedStatus(updatedCase.status);
      setStaffNote(updatedCase.staff_note);
      void queryClient.invalidateQueries({ queryKey: ["staff-after-sales-cases"] });
      toast.success("工单已保存。 ");
    },
    onError: (error) => toast.error(getErrorMessage(error, "工单保存失败，请稍后重试。")),
  });

  const shipOrderMutation = useMutation({
    mutationFn: (caseId: string) => afterSalesApi.shipStaffCaseOrder(caseId),
    onSuccess: (updatedCase) => {
      queryClient.setQueryData(["staff-after-sales-case", updatedCase.id], updatedCase);
      void queryClient.invalidateQueries({ queryKey: ["staff-after-sales-cases"] });
      toast.success("订单已标记为已发货。 ");
    },
    onError: (error) => toast.error(getErrorMessage(error, "订单发货失败，请稍后重试。")),
  });

  const refundOrderMutation = useMutation({
    mutationFn: (caseId: string) => afterSalesApi.refundStaffCaseOrder(caseId),
    onSuccess: (updatedCase) => {
      queryClient.setQueryData(["staff-after-sales-case", updatedCase.id], updatedCase);
      setSelectedStatus(updatedCase.status);
      setStaffNote(updatedCase.staff_note);
      void queryClient.invalidateQueries({ queryKey: ["staff-after-sales-cases"] });
      void queryClient.invalidateQueries({ queryKey: ["staff-orders"] });
      toast.success("订单已标记为已退款，工单已关闭。 ");
    },
    onError: (error) => toast.error(getErrorMessage(error, "退款标记失败，请稍后重试。")),
  });

  const shipStandaloneOrderMutation = useMutation({
    mutationFn: (orderId: string) => afterSalesApi.shipStaffOrder(orderId),
    onSuccess: (updatedOrder) => {
      queryClient.setQueryData<StaffOrder[]>(["staff-orders", orderFilters], (current) =>
        current?.map((order) => (order.id === updatedOrder.id ? updatedOrder : order)),
      );
      toast.success("订单已标记为已发货。 ");
    },
    onError: (error) => toast.error(getErrorMessage(error, "订单发货失败，请稍后重试。")),
  });

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!user?.is_staff) {
    return <Navigate to="/" replace />;
  }

  const selectedCase = selectedCaseQuery.data;
  const allowedStatusOptions = selectedCase
    ? STATUS_OPTIONS.filter((option) => STAFF_STATUS_TRANSITIONS[selectedCase.status].includes(option.value))
    : STATUS_OPTIONS;
  const hasChanges = Boolean(
    selectedCase &&
      (selectedStatus !== selectedCase.status || staffNote !== selectedCase.staff_note),
  );
  const canShipOrder = selectedCase?.order?.status === "PAID";
  const canRefundOrder = Boolean(
    selectedCase?.order &&
      (selectedCase.case_type === "REFUND" || selectedCase.case_type === "RETURN_REFUND") &&
      selectedCase.status === "APPROVED" &&
      (selectedCase.order.status === "PAID" || selectedCase.order.status === "SHIPPED"),
  );
  const selectedOrder = ordersQuery.data?.find((order) => order.id === selectedOrderId) ?? null;

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSearch(searchDraft.trim());
  };

  const saveCase = () => {
    if (!selectedCase || !hasChanges) return;
    updateMutation.mutate({
      caseId: selectedCase.id,
      status: selectedStatus,
      staffNote,
    });
  };

  const submitOrderSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setOrderSearch(orderSearchDraft.trim());
  };

  const refreshCurrentView = () => {
    if (activeView === "orders") {
      void ordersQuery.refetch();
      return;
    }
    void casesQuery.refetch();
  };

  const isRefreshing = activeView === "orders" ? ordersQuery.isFetching : casesQuery.isFetching;

  return (
    <Container className="py-6 sm:py-8">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-accent/15 text-accent">
            <ClipboardList className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-semibold text-ink">客服工作台</h1>
            <p className="text-sm text-ink-muted">{user.username}</p>
          </div>
        </div>
        <Button
          variant="outline"
          size="icon"
          onClick={refreshCurrentView}
          isLoading={isRefreshing}
          aria-label="刷新当前队列"
          title="刷新当前队列"
        >
          {!isRefreshing && <RefreshCw className="h-4 w-4" />}
        </Button>
      </div>

      <div role="tablist" aria-label="工作台视图" className="mb-4 flex border-b border-border">
        <button
          type="button"
          role="tab"
          aria-selected={activeView === "cases"}
          onClick={() => setActiveView("cases")}
          className={cn(
            "border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
            activeView === "cases" ? "border-accent text-ink" : "border-transparent text-ink-muted hover:text-ink",
          )}
        >
          售后工单
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeView === "orders"}
          onClick={() => setActiveView("orders")}
          className={cn(
            "border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
            activeView === "orders" ? "border-accent text-ink" : "border-transparent text-ink-muted hover:text-ink",
          )}
        >
          订单发货
        </button>
      </div>

      {activeView === "cases" ? (
      <section className="overflow-hidden rounded-lg border border-border bg-bg-surface shadow-panel">
        <div className="grid gap-2 border-b border-border p-3 sm:grid-cols-[minmax(150px,1fr)_180px_180px_auto] sm:items-center">
          <form onSubmit={submitSearch} className="flex min-w-0 items-center gap-2">
            <input
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
              maxLength={100}
              placeholder="搜索工单、用户或原因"
              aria-label="搜索工单"
              className="h-9 min-w-0 flex-1 rounded-md border border-border-strong bg-bg px-3 text-sm text-ink outline-none placeholder:text-ink-faint focus:border-accent"
            />
            <Button type="submit" variant="ghost" size="icon" aria-label="搜索" title="搜索">
              <Search className="h-4 w-4" />
            </Button>
          </form>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            aria-label="按工单状态筛选"
            className="h-9 rounded-md border border-border-strong bg-bg px-3 text-sm text-ink outline-none focus:border-accent"
          >
            <option value="">全部状态</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            value={priorityFilter}
            onChange={(event) => setPriorityFilter(event.target.value)}
            aria-label="按优先级筛选"
            className="h-9 rounded-md border border-border-strong bg-bg px-3 text-sm text-ink outline-none focus:border-accent"
          >
            <option value="">全部优先级</option>
            {PRIORITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="px-1 text-right font-mono text-xs text-ink-muted">
            {casesQuery.data?.length ?? 0} 条
          </p>
        </div>

        <div className="grid min-h-[650px] xl:grid-cols-[300px_minmax(0,1fr)_320px]">
          <aside className="border-b border-border xl:border-b-0 xl:border-r">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-ink">工单队列</h2>
            </div>
            <div className="max-h-[310px] overflow-y-auto xl:max-h-[720px]">
              {casesQuery.isLoading ? (
                <div className="flex items-center gap-2 p-4 text-sm text-ink-muted">
                  <Loader2 className="h-4 w-4 animate-spin" /> 正在载入
                </div>
              ) : casesQuery.isError ? (
                <p className="p-4 text-sm leading-6 text-danger">工单队列加载失败，请刷新后重试。</p>
              ) : casesQuery.data?.length ? (
                casesQuery.data.map((afterSalesCase) => (
                  <button
                    key={afterSalesCase.id}
                    type="button"
                    onClick={() => setSelectedCaseId(afterSalesCase.id)}
                    className={cn(
                      "block w-full border-b border-border px-4 py-3 text-left transition-colors last:border-b-0",
                      selectedCaseId === afterSalesCase.id
                        ? "bg-accent/10"
                        : "hover:bg-white/[0.04]",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs text-accent">{afterSalesCase.case_number}</span>
                      <Badge variant={priorityVariant(afterSalesCase.priority)}>{priorityLabel(afterSalesCase.priority)}</Badge>
                    </div>
                    <p className="mt-2 truncate text-sm font-medium text-ink">{afterSalesCase.user.username}</p>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-ink-muted">{afterSalesCase.reason}</p>
                    <p className="mt-2 text-xs text-ink-faint">{afterSalesCase.status_label}</p>
                  </button>
                ))
              ) : (
                <p className="p-4 text-sm leading-6 text-ink-muted">当前筛选条件下没有工单。</p>
              )}
            </div>
          </aside>

          <main className="min-w-0 border-b border-border xl:border-b-0 xl:border-r">
            {selectedCaseQuery.isLoading ? (
              <div className="flex h-full items-center justify-center gap-2 text-sm text-ink-muted">
                <Loader2 className="h-4 w-4 animate-spin" /> 正在读取工单
              </div>
            ) : selectedCase ? (
              <div className="flex h-full flex-col">
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
                  <div>
                    <p className="font-mono text-xs text-accent">{selectedCase.case_number}</p>
                    <h2 className="mt-1 text-base font-semibold text-ink">{selectedCase.case_type_label}</h2>
                  </div>
                  <div className="flex flex-wrap justify-end gap-2">
                    <Badge variant="outline">{selectedCase.status_label}</Badge>
                    <Badge variant={priorityVariant(selectedCase.priority)}>{priorityLabel(selectedCase.priority)}</Badge>
                  </div>
                </div>

                <div className="flex-1 space-y-5 overflow-y-auto p-4 sm:p-5">
                  <section>
                    <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <FileText className="h-4 w-4 text-accent" /> 用户申请
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-ink-muted">{selectedCase.reason}</p>
                  </section>

                  <section className="border-t border-border pt-5">
                    <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <UserRound className="h-4 w-4 text-accent" /> 用户信息
                    </div>
                    <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                      <div>
                        <dt className="text-xs text-ink-faint">用户名</dt>
                        <dd className="mt-1 text-ink">{selectedCase.user.username}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-ink-faint">手机号</dt>
                        <dd className="mt-1 text-ink">{selectedCase.user.phone_number || "未提供"}</dd>
                      </div>
                    </dl>
                  </section>

                  <section className="border-t border-border pt-5">
                    <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <Package className="h-4 w-4 text-accent" /> 关联订单
                    </div>
                    {selectedCase.order ? (
                      <div className="mt-3 space-y-3 text-sm">
                        <div className="flex flex-wrap justify-between gap-2 text-ink-muted">
                          <span className="break-all font-mono text-xs">{selectedCase.order.id}</span>
                          <span>{formatPrice(selectedCase.order.total_amount)}</span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs text-ink-faint">订单状态</span>
                          <Badge variant={selectedCase.order.status === "SHIPPED" ? "accent" : "default"}>
                            {ORDER_STATUS_LABEL[selectedCase.order.status] ?? selectedCase.order.status}
                          </Badge>
                        </div>
                        <ul className="divide-y divide-border border-y border-border">
                          {selectedCase.order.items.map((item) => (
                            <li key={`${item.product_name}-${item.quantity}`} className="flex justify-between gap-3 py-2 text-ink-muted">
                              <span>{item.product_name}</span>
                              <span className="shrink-0">x{item.quantity}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <p className="mt-2 text-sm text-ink-muted">未关联订单</p>
                    )}
                  </section>

                  <section className="border-t border-border pt-5">
                    <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <Bot className="h-4 w-4 text-accent" /> Agent 摘要
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-ink-muted">
                      {selectedCase.agent_summary || "暂无摘要"}
                    </p>
                  </section>

                  <section className="border-t border-border pt-5">
                    <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <Bot className="h-4 w-4 text-accent" /> 用户对话
                    </div>
                    {selectedCase.conversation?.summary && (
                      <p className="mt-2 text-xs leading-5 text-ink-faint">{selectedCase.conversation.summary}</p>
                    )}
                    {selectedCase.conversation?.messages.length ? (
                      <div className="mt-3 space-y-3">
                        {selectedCase.conversation.messages.map((message) => {
                          const isCustomer = message.role === "USER";
                          return (
                            <div key={message.id} className={cn("flex gap-2", isCustomer && "flex-row-reverse")}>
                              <div
                                className={cn(
                                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-md",
                                  isCustomer ? "bg-coral/15 text-coral" : "bg-accent/15 text-accent",
                                )}
                              >
                                {isCustomer ? <UserRound className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
                              </div>
                              <div className={cn("min-w-0", isCustomer && "text-right")}>
                                <p className="whitespace-pre-wrap text-sm leading-6 text-ink-muted">{message.content}</p>
                                <p className="mt-1 text-xs text-ink-faint">{formatDateTime(message.created_at)}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="mt-2 text-sm text-ink-muted">暂无可展示的对话记录。</p>
                    )}
                  </section>
                </div>
              </div>
            ) : (
              <div className="flex h-full items-center justify-center p-6 text-center text-sm text-ink-muted">
                从左侧选择一张工单。
              </div>
            )}
          </main>

          <aside className="min-w-0">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-ink">人工处理</h2>
            </div>
            {selectedCase ? (
              <div className="space-y-5 p-4">
                <dl className="grid gap-3 text-sm">
                  <div>
                    <dt className="text-xs text-ink-faint">处理人</dt>
                    <dd className="mt-1 text-ink">{selectedCase.assigned_to?.username ?? "尚未分配"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-ink-faint">创建时间</dt>
                    <dd className="mt-1 text-ink">{formatDateTime(selectedCase.created_at)}</dd>
                  </div>
                  {selectedCase.resolved_at && (
                    <div>
                      <dt className="text-xs text-ink-faint">完成时间</dt>
                      <dd className="mt-1 text-ink">{formatDateTime(selectedCase.resolved_at)}</dd>
                    </div>
                  )}
                </dl>

                {selectedCase.order && (
                  <section className="border-t border-border pt-5">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="text-sm font-medium text-ink">订单发货</h3>
                      <Badge variant={selectedCase.order.status === "SHIPPED" ? "accent" : "default"}>
                        {ORDER_STATUS_LABEL[selectedCase.order.status] ?? selectedCase.order.status}
                      </Badge>
                    </div>
                    {canShipOrder && (
                      <Button
                        variant="secondary"
                        className="mt-3 w-full"
                        onClick={() => shipOrderMutation.mutate(selectedCase.id)}
                        isLoading={shipOrderMutation.isPending}
                      >
                        {!shipOrderMutation.isPending && <Truck className="h-4 w-4" />}
                        标记为已发货
                      </Button>
                    )}
                  </section>
                )}

                {selectedCase.order && (
                  <section className="border-t border-border pt-5">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="text-sm font-medium text-ink">退款处理</h3>
                      <Badge variant={selectedCase.order.status === "REFUNDED" ? "success" : "default"}>
                        {ORDER_STATUS_LABEL[selectedCase.order.status] ?? selectedCase.order.status}
                      </Badge>
                    </div>
                    {canRefundOrder && (
                      <Button
                        variant="secondary"
                        className="mt-3 w-full"
                        onClick={() => refundOrderMutation.mutate(selectedCase.id)}
                        isLoading={refundOrderMutation.isPending}
                      >
                        {!refundOrderMutation.isPending && <RotateCcw className="h-4 w-4" />}
                        标记为已退款
                      </Button>
                    )}
                  </section>
                )}

                <div className="border-t border-border pt-5">
                  <label htmlFor="staff-case-status" className="text-sm font-medium text-ink">
                    处理状态
                  </label>
                  <select
                    id="staff-case-status"
                    value={selectedStatus}
                    onChange={(event) => setSelectedStatus(event.target.value as AfterSalesCaseStatus)}
                    className="mt-2 h-10 w-full rounded-md border border-border-strong bg-bg px-3 text-sm text-ink outline-none focus:border-accent"
                  >
                    {allowedStatusOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="staff-case-note" className="text-sm font-medium text-ink">
                    客服备注
                  </label>
                  <textarea
                    id="staff-case-note"
                    value={staffNote}
                    onChange={(event) => setStaffNote(event.target.value)}
                    maxLength={2000}
                    rows={8}
                    placeholder="填写本次处理记录"
                    className="mt-2 w-full resize-y rounded-md border border-border-strong bg-bg px-3 py-2 text-sm leading-6 text-ink outline-none placeholder:text-ink-faint focus:border-accent"
                  />
                </div>

                <Button className="w-full" onClick={saveCase} disabled={!hasChanges} isLoading={updateMutation.isPending}>
                  {!updateMutation.isPending && <Save className="h-4 w-4" />}
                  保存处理结果
                </Button>
              </div>
            ) : (
              <p className="p-4 text-sm text-ink-muted">选择工单后可填写处理结果。</p>
            )}
          </aside>
        </div>
      </section>
      ) : (
        <OrderFulfillmentPanel
          orders={ordersQuery.data ?? []}
          isLoading={ordersQuery.isLoading}
          isError={ordersQuery.isError}
          statusFilter={orderStatusFilter}
          searchDraft={orderSearchDraft}
          selectedOrderId={selectedOrderId}
          selectedOrder={selectedOrder}
          isShipping={shipStandaloneOrderMutation.isPending}
          onStatusFilterChange={setOrderStatusFilter}
          onSearchDraftChange={setOrderSearchDraft}
          onSearch={submitOrderSearch}
          onSelectOrder={setSelectedOrderId}
          onShip={(orderId) => shipStandaloneOrderMutation.mutate(orderId)}
        />
      )}
    </Container>
  );
}

interface OrderFulfillmentPanelProps {
  orders: StaffOrder[];
  isLoading: boolean;
  isError: boolean;
  statusFilter: string;
  searchDraft: string;
  selectedOrderId: string | null;
  selectedOrder: StaffOrder | null;
  isShipping: boolean;
  onStatusFilterChange: (value: string) => void;
  onSearchDraftChange: (value: string) => void;
  onSearch: (event: FormEvent<HTMLFormElement>) => void;
  onSelectOrder: (orderId: string) => void;
  onShip: (orderId: string) => void;
}

function OrderFulfillmentPanel({
  orders,
  isLoading,
  isError,
  statusFilter,
  searchDraft,
  selectedOrderId,
  selectedOrder,
  isShipping,
  onStatusFilterChange,
  onSearchDraftChange,
  onSearch,
  onSelectOrder,
  onShip,
}: OrderFulfillmentPanelProps) {
  const canShip = selectedOrder?.status === "PAID";

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-bg-surface shadow-panel">
      <div className="grid gap-2 border-b border-border p-3 sm:grid-cols-[minmax(180px,1fr)_180px_auto] sm:items-center">
        <form onSubmit={onSearch} className="flex min-w-0 items-center gap-2">
          <input
            value={searchDraft}
            onChange={(event) => onSearchDraftChange(event.target.value)}
            maxLength={100}
            placeholder="搜索用户或商品"
            aria-label="搜索订单"
            className="h-9 min-w-0 flex-1 rounded-md border border-border-strong bg-bg px-3 text-sm text-ink outline-none placeholder:text-ink-faint focus:border-accent"
          />
          <Button type="submit" variant="ghost" size="icon" aria-label="搜索" title="搜索">
            <Search className="h-4 w-4" />
          </Button>
        </form>
        <select
          value={statusFilter}
          onChange={(event) => onStatusFilterChange(event.target.value)}
          aria-label="按订单状态筛选"
          className="h-9 rounded-md border border-border-strong bg-bg px-3 text-sm text-ink outline-none focus:border-accent"
        >
          <option value="">全部订单状态</option>
          {ORDER_STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <p className="px-1 text-right font-mono text-xs text-ink-muted">{orders.length} 条</p>
      </div>

      <div className="grid min-h-[650px] lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="border-b border-border lg:border-b-0 lg:border-r">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold text-ink">订单队列</h2>
          </div>
          <div className="max-h-[320px] overflow-y-auto lg:max-h-[720px]">
            {isLoading ? (
              <div className="flex items-center gap-2 p-4 text-sm text-ink-muted">
                <Loader2 className="h-4 w-4 animate-spin" /> 正在载入
              </div>
            ) : isError ? (
              <p className="p-4 text-sm leading-6 text-danger">订单队列加载失败，请刷新后重试。</p>
            ) : orders.length ? (
              orders.map((order) => (
                <button
                  key={order.id}
                  type="button"
                  onClick={() => onSelectOrder(order.id)}
                  className={cn(
                    "block w-full border-b border-border px-4 py-3 text-left transition-colors last:border-b-0",
                    selectedOrderId === order.id ? "bg-accent/10" : "hover:bg-white/[0.04]",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-accent">{order.id.slice(0, 8)}</span>
                    <Badge variant={orderStatusVariant(order.status)}>
                      {ORDER_STATUS_LABEL[order.status] ?? order.status}
                    </Badge>
                  </div>
                  <p className="mt-2 truncate text-sm font-medium text-ink">{order.user.username}</p>
                  <p className="mt-1 truncate text-xs text-ink-muted">
                    {order.items.map((item) => item.product_name).join("、") || "无商品明细"}
                  </p>
                  <p className="mt-2 font-mono text-xs text-ink-faint">{formatPrice(order.total_amount)}</p>
                </button>
              ))
            ) : (
              <p className="p-4 text-sm leading-6 text-ink-muted">当前筛选条件下没有订单。</p>
            )}
          </div>
        </aside>

        <main className="min-w-0">
          {selectedOrder ? (
            <div className="flex h-full flex-col">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
                <div className="min-w-0">
                  <p className="break-all font-mono text-xs text-accent">{selectedOrder.id}</p>
                  <h2 className="mt-1 text-base font-semibold text-ink">订单履约</h2>
                </div>
                <Badge variant={orderStatusVariant(selectedOrder.status)}>
                  {ORDER_STATUS_LABEL[selectedOrder.status] ?? selectedOrder.status}
                </Badge>
              </div>

              <div className="flex-1 space-y-5 overflow-y-auto p-4 sm:p-5">
                <section>
                  <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <UserRound className="h-4 w-4 text-accent" /> 收件人
                  </div>
                  <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="text-xs text-ink-faint">用户</dt>
                      <dd className="mt-1 text-ink">{selectedOrder.user.username}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-ink-faint">手机号</dt>
                      <dd className="mt-1 text-ink">{selectedOrder.user.phone_number || "未提供"}</dd>
                    </div>
                  </dl>
                </section>

                <section className="border-t border-border pt-5">
                  <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <Package className="h-4 w-4 text-accent" /> 收货地址
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-ink-muted">
                    {selectedOrder.shipping_address || "未填写收货地址"}
                  </p>
                </section>

                <section className="border-t border-border pt-5">
                  <div className="flex items-center justify-between gap-3 text-sm font-semibold text-ink">
                    <span className="flex items-center gap-2"><Package className="h-4 w-4 text-accent" /> 商品明细</span>
                    <span className="font-mono">{formatPrice(selectedOrder.total_amount)}</span>
                  </div>
                  <ul className="mt-3 divide-y divide-border border-y border-border">
                    {selectedOrder.items.map((item, index) => (
                      <li key={`${item.product_name}-${index}`} className="flex items-start justify-between gap-4 py-3 text-sm">
                        <div className="min-w-0">
                          <p className="text-ink">{item.product_name}</p>
                          <p className="mt-1 font-mono text-xs text-ink-faint">{formatPrice(item.unit_price)} x {item.quantity}</p>
                        </div>
                        <span className="shrink-0 font-mono text-ink-muted">{formatPrice(item.line_total)}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              </div>

              <div className="border-t border-border p-4 sm:flex sm:items-center sm:justify-between sm:gap-4">
                <p className="text-xs text-ink-faint">下单时间：{formatDateTime(selectedOrder.created_at)}</p>
                {canShip && (
                  <Button
                    className="mt-3 w-full sm:mt-0 sm:w-auto"
                    onClick={() => onShip(selectedOrder.id)}
                    isLoading={isShipping}
                  >
                    {!isShipping && <Truck className="h-4 w-4" />}
                    标记为已发货
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center p-6 text-center text-sm text-ink-muted">
              从左侧选择一笔订单。
            </div>
          )}
        </main>
      </div>
    </section>
  );
}
