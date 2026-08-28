import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, MessageCircleMore, Plus, Send, UserRound } from "lucide-react";
import { Navigate } from "react-router-dom";
import { afterSalesApi } from "@/api/afterSales";
import { getErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { useAuth } from "@/hooks/useAuth";
import { toast } from "@/store/toastStore";
import type { AgentMessage } from "@/types";
import { cn } from "@/utils/cn";

const STORAGE_KEY = "aperture-after-sales-conversation-id";

function getStoredConversationId(): string | null {
  return window.localStorage.getItem(STORAGE_KEY);
}

export function AfterSalesAgent() {
  const { isAuthenticated, user } = useAuth();
  const [conversationId, setConversationId] = useState<string | null>(getStoredConversationId);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [draft, setDraft] = useState("");
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const conversationQuery = useQuery({
    queryKey: ["after-sales-conversation", conversationId],
    queryFn: () => afterSalesApi.getConversation(conversationId!),
    enabled: Boolean(conversationId && isAuthenticated),
    retry: false,
  });

  useEffect(() => {
    if (conversationQuery.data) {
      setMessages(conversationQuery.data.messages);
    }
  }, [conversationQuery.data]);

  useEffect(() => {
    if (conversationQuery.isError) {
      window.localStorage.removeItem(STORAGE_KEY);
      setConversationId(null);
      setMessages([]);
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
    mutationFn: (message: string) => afterSalesApi.sendMessage({ message, conversation_id: conversationId }),
    onSuccess: (response, sentMessage) => {
      window.localStorage.setItem(STORAGE_KEY, response.conversation_id);
      setConversationId(response.conversation_id);
      setMessages((current) => [
        ...current.map((item) =>
          item.id === `pending-${sentMessage}` ? { ...item, id: `user-${Date.now()}` } : item,
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
      setMessages((current) => current.filter((item) => item.id !== `pending-${sentMessage}`));
      toast.error(getErrorMessage(error, "售后助手暂时不可用，请稍后重试。"));
    },
  });

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const displayMessages = messages.length ? messages : [introMessage];

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || sendMutation.isPending) return;

    setMessages((current) => [
      ...current,
      { id: `pending-${message}`, role: "USER", content: message, created_at: new Date().toISOString() },
    ]);
    setDraft("");
    sendMutation.mutate(message);
  };

  const startNewConversation = () => {
    window.localStorage.removeItem(STORAGE_KEY);
    setConversationId(null);
    setMessages([]);
    setDraft("");
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
    </Container>
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
