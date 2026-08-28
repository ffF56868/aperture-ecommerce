import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Check,
  CircleCheck,
  ClipboardCheck,
  Clock3,
  MessageCircleMore,
  Plus,
  Send,
  UserRound,
  X,
} from "lucide-react";
import { Navigate } from "react-router-dom";
import { afterSalesApi } from "@/api/afterSales";
import { getErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { useAuth } from "@/hooks/useAuth";
import { toast } from "@/store/toastStore";
import type { AfterSalesCase, AfterSalesConfirmation, AgentMessage } from "@/types";
import { cn } from "@/utils/cn";

const STORAGE_KEY = "aperture-after-sales-conversation-id";

function getStoredConversationId(): string | null {
  return window.localStorage.getItem(STORAGE_KEY);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function AfterSalesAgent() {
  const { isAuthenticated, user } = useAuth();
  const [conversationId, setConversationId] = useState<string | null>(getStoredConversationId);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [pendingConfirmation, setPendingConfirmation] = useState<AfterSalesConfirmation | null>(null);
  const [recentCases, setRecentCases] = useState<AfterSalesCase[]>([]);
  const [workflowMessage, setWorkflowMessage] = useState("");
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const conversationQuery = useQuery({
    queryKey: ["after-sales-conversation", conversationId],
    queryFn: () => afterSalesApi.getConversation(conversationId!),
    enabled: Boolean(conversationId && isAuthenticated),
    retry: false,
    refetchInterval: 15_000,
  });

  useEffect(() => {
    if (conversationQuery.data) {
      setMessages(conversationQuery.data.messages);
      setPendingConfirmation(conversationQuery.data.pending_confirmation);
      setRecentCases(conversationQuery.data.recent_cases);
    }
  }, [conversationQuery.data]);

  useEffect(() => {
    if (conversationQuery.isError) {
      window.localStorage.removeItem(STORAGE_KEY);
      setConversationId(null);
      setMessages([]);
      setPendingConfirmation(null);
      setRecentCases([]);
    }
  }, [conversationQuery.isError]);

  useEffect(() => {
    const chatScroll = chatScrollRef.current;
    if (!chatScroll) return;

    const distanceFromBottom = chatScroll.scrollHeight - chatScroll.scrollTop - chatScroll.clientHeight;
    if (distanceFromBottom < 120) {
      chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  const introMessage = useMemo<AgentMessage>(
    () => ({
      id: "intro",
      role: "ASSISTANT",
      content: `你好，${user?.username ?? ""}。请告诉我需要核验的售后问题。`,
      created_at: new Date().toISOString(),
    }),
    [user?.username],
  );

  const sendMutation = useMutation({
    mutationFn: ({ message }: { id: string; message: string }) =>
      afterSalesApi.sendMessage({ message, conversation_id: conversationId }),
    onSuccess: (response, sentMessage) => {
      window.localStorage.setItem(STORAGE_KEY, response.conversation_id);
      setConversationId(response.conversation_id);
      setPendingConfirmation(response.pending_confirmation);
      setRecentCases(response.recent_cases);
      setWorkflowMessage("");
      setMessages((current) => [
        ...current.map((item) =>
          item.id === sentMessage.id ? { ...item, id: `user-${Date.now()}` } : item,
        ),
        {
          id: `assistant-${Date.now()}`,
          role: "ASSISTANT",
          content: response.assistant_message,
          created_at: new Date().toISOString(),
        },
      ]);
    },
    onError: (error, sentMessage) => {
      setMessages((current) => [
        ...current.map((item) =>
          item.id === sentMessage.id ? { ...item, id: `user-failed-${Date.now()}` } : item,
        ),
        {
          id: `assistant-error-${Date.now()}`,
          role: "ASSISTANT",
          content: getErrorMessage(error, "这次请求没有成功，请稍后重试。"),
          created_at: new Date().toISOString(),
        },
      ]);
      toast.error(getErrorMessage(error, "售后助手暂时不可用，请稍后重试。"));
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (confirmationId: string) => afterSalesApi.confirmConfirmation(confirmationId),
    onSuccess: (response) => {
      setPendingConfirmation(null);
      setWorkflowMessage(response.message);
      if (response.after_sales_case) {
        setRecentCases((current) => [
          response.after_sales_case!,
          ...current.filter((item) => item.id !== response.after_sales_case!.id),
        ]);
      }
      toast.success(response.message);
      void queryClient.invalidateQueries({ queryKey: ["after-sales-conversation", conversationId] });
    },
    onError: (error) => toast.error(getErrorMessage(error, "确认提交失败，请重新发起申请。")),
  });

  const rejectMutation = useMutation({
    mutationFn: (confirmationId: string) => afterSalesApi.rejectConfirmation(confirmationId),
    onSuccess: (response) => {
      setPendingConfirmation(null);
      setWorkflowMessage(response.message);
      toast.info(response.message);
      void queryClient.invalidateQueries({ queryKey: ["after-sales-conversation", conversationId] });
    },
    onError: (error) => toast.error(getErrorMessage(error, "取消申请失败，请稍后重试。")),
  });

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const displayMessages = messages.length ? messages : [introMessage];

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || sendMutation.isPending) return;

    const messageId = `pending-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setMessages((current) => [
      ...current,
      { id: messageId, role: "USER", content: message, created_at: new Date().toISOString() },
    ]);
    setDraft("");
    sendMutation.mutate({ id: messageId, message });
  };

  const startNewConversation = () => {
    window.localStorage.removeItem(STORAGE_KEY);
    setConversationId(null);
    setMessages([]);
    setDraft("");
    setPendingConfirmation(null);
    setWorkflowMessage("");
  };

  return (
    <Container className="py-8 sm:py-10">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-accent/15 text-accent">
            <MessageCircleMore className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="font-display text-2xl font-semibold text-ink">售后助手</h1>
            <p className="truncate text-sm text-ink-muted">{user?.username}</p>
          </div>
        </div>
        <Button variant="outline" size="icon" onClick={startNewConversation} title="新建会话" aria-label="新建会话">
          <Plus className="h-4 w-4" />
        </Button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <section className="flex h-[min(680px,calc(100vh-190px))] min-h-[500px] flex-col overflow-hidden rounded-lg border border-border bg-bg-surface shadow-panel">
          <div ref={chatScrollRef} className="flex-1 space-y-5 overflow-y-auto p-4 sm:p-6">
            {conversationQuery.isLoading && (
              <div className="text-center text-sm text-ink-muted">正在载入会话…</div>
            )}
            {displayMessages.map((message) => (
              <ChatBubble key={message.id} message={message} />
            ))}
            {sendMutation.isPending && (
              <div className="flex items-center gap-2 text-sm text-ink-muted">
                <Bot className="h-4 w-4 text-accent" />
                正在查询…
              </div>
            )}
          </div>

          <form onSubmit={submit} className="border-t border-border p-3 sm:p-4">
            <div className="flex items-end gap-2">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                maxLength={2000}
                rows={2}
                placeholder="输入售后问题"
                className="min-h-10 flex-1 resize-none rounded-md border border-border-strong bg-bg px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-accent"
              />
              <Button type="submit" size="icon" isLoading={sendMutation.isPending} aria-label="发送" title="发送">
                {!sendMutation.isPending && <Send className="h-4 w-4" />}
              </Button>
            </div>
          </form>
        </section>

        <AfterSalesWorkflowPanel
          pendingConfirmation={pendingConfirmation}
          recentCases={recentCases}
          workflowMessage={workflowMessage}
          isPending={confirmMutation.isPending || rejectMutation.isPending}
          onConfirm={(confirmationId) => confirmMutation.mutate(confirmationId)}
          onReject={(confirmationId) => rejectMutation.mutate(confirmationId)}
        />
      </div>
    </Container>
  );
}

interface AfterSalesWorkflowPanelProps {
  pendingConfirmation: AfterSalesConfirmation | null;
  recentCases: AfterSalesCase[];
  workflowMessage: string;
  isPending: boolean;
  onConfirm: (confirmationId: string) => void;
  onReject: (confirmationId: string) => void;
}

function AfterSalesWorkflowPanel({
  pendingConfirmation,
  recentCases,
  workflowMessage,
  isPending,
  onConfirm,
  onReject,
}: AfterSalesWorkflowPanelProps) {
  const itemSummary = pendingConfirmation?.order?.items
    .map((item) => `${item.product_name} x${item.quantity}`)
    .join("、");

  return (
    <aside className="flex h-fit max-h-[680px] min-h-[220px] flex-col overflow-hidden rounded-lg border border-border bg-bg-surface shadow-panel lg:h-[min(680px,calc(100vh-190px))]">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <ClipboardCheck className="h-4 w-4 text-accent" />
        <h2 className="text-sm font-semibold text-ink">售后处理</h2>
      </div>

      <div className="space-y-4 overflow-y-auto p-4">
        {pendingConfirmation ? (
          <section aria-live="polite" className="border border-accent/35 bg-accent/5 p-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Clock3 className="h-4 w-4 text-accent" />
              待你确认
            </div>
            <p className="mt-3 text-sm font-medium text-ink">{pendingConfirmation.action_label}</p>
            <dl className="mt-3 space-y-2 text-xs leading-5 text-ink-muted">
              <div>
                <dt className="text-ink-faint">订单</dt>
                <dd className="break-all text-ink">{pendingConfirmation.order?.id ?? "未关联订单"}</dd>
              </div>
              {itemSummary && (
                <div>
                  <dt className="text-ink-faint">商品</dt>
                  <dd className="text-ink">{itemSummary}</dd>
                </div>
              )}
              {pendingConfirmation.order && (
                <div>
                  <dt className="text-ink-faint">金额</dt>
                  <dd className="text-ink">￥{pendingConfirmation.order.total_amount}</dd>
                </div>
              )}
              <div>
                <dt className="text-ink-faint">原因</dt>
                <dd className="text-ink">{pendingConfirmation.reason}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">有效期至</dt>
                <dd className="text-ink">{formatDate(pendingConfirmation.expires_at)}</dd>
              </div>
            </dl>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <Button
                size="sm"
                isLoading={isPending}
                onClick={() => onConfirm(pendingConfirmation.id)}
                className="w-full"
              >
                {!isPending && <Check className="h-4 w-4" />}
                确认提交
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={isPending}
                onClick={() => onReject(pendingConfirmation.id)}
                className="w-full"
              >
                <X className="h-4 w-4" />
                取消
              </Button>
            </div>
          </section>
        ) : workflowMessage ? (
          <div className="flex items-start gap-2 border border-success/30 bg-success/10 p-3 text-sm leading-5 text-ink">
            <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
            <p>{workflowMessage}</p>
          </div>
        ) : (
          <p className="text-sm leading-6 text-ink-muted">当前没有待确认的售后申请。</p>
        )}

        <section className="border-t border-border pt-4">
          <h3 className="text-sm font-semibold text-ink">近期工单</h3>
          {recentCases.length ? (
            <ul className="mt-3 divide-y divide-border">
              {recentCases.map((afterSalesCase) => (
                <li key={afterSalesCase.id} className="py-3 first:pt-0">
                  <p className="font-mono text-xs text-accent">{afterSalesCase.case_number}</p>
                  <p className="mt-1 text-sm text-ink">{afterSalesCase.case_type_label}</p>
                  <p className="mt-1 text-xs text-ink-muted">{afterSalesCase.status_label}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-ink-muted">暂无工单</p>
          )}
        </section>
      </div>
    </aside>
  );
}

function ChatBubble({ message }: { message: AgentMessage }) {
  const isUser = message.role === "USER";
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-md",
          isUser ? "bg-coral/15 text-coral" : "bg-accent/15 text-accent",
        )}
      >
        {isUser ? <UserRound className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <p
        className={cn(
          "max-w-[80%] whitespace-pre-wrap rounded-md px-3 py-2.5 text-sm leading-6",
          isUser ? "bg-accent text-white" : "bg-bg-elevated text-ink",
        )}
      >
        {message.content}
      </p>
    </div>
  );
}
