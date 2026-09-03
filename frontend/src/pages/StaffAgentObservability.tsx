import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  Clock3,
  Eye,
  Filter,
  GitBranch,
  RefreshCw,
  Search,
  ShieldAlert,
  UserRound,
  XCircle,
} from "lucide-react";
import { Navigate } from "react-router-dom";
import { afterSalesApi, type AgentRunFilters } from "@/api/afterSales";
import { getErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Container } from "@/components/ui/Container";
import { EmptyState } from "@/components/common/EmptyState";
import { Spinner } from "@/components/ui/Skeleton";
import { useAuth } from "@/hooks/useAuth";
import type { AgentRunDetail, AgentRunEvent, AgentRunListItem, AgentRunStatus } from "@/types";
import { formatDateTime } from "@/utils/format";

const STATUS_OPTIONS: Array<{ value: AgentRunStatus | ""; label: string }> = [
  { value: "", label: "全部状态" },
  { value: "SUCCEEDED", label: "已完成" },
  { value: "AWAITING_CONFIRMATION", label: "等待确认" },
  { value: "ESCALATED", label: "已转人工" },
  { value: "BLOCKED", label: "已拦截" },
  { value: "FAILED", label: "失败" },
];

const INTENT_OPTIONS = [
  { value: "", label: "全部意图" },
  { value: "ORDER_QUERY", label: "订单查询" },
  { value: "REFUND", label: "退款" },
  { value: "RETURN_REFUND", label: "退货退款" },
  { value: "QUALITY_ISSUE", label: "质量问题" },
  { value: "DELIVERY_ISSUE", label: "物流问题" },
  { value: "KNOWLEDGE_QUERY", label: "知识问答" },
  { value: "GENERAL", label: "其他" },
];

const STATUS_VARIANT: Record<AgentRunStatus, "default" | "accent" | "coral" | "success" | "danger"> = {
  RUNNING: "accent",
  SUCCEEDED: "success",
  AWAITING_CONFIRMATION: "coral",
  ESCALATED: "coral",
  BLOCKED: "danger",
  FAILED: "danger",
};

const INTENT_LABEL: Record<string, string> = Object.fromEntries(
  INTENT_OPTIONS.filter((option) => option.value).map((option) => [option.value, option.label]),
);

function formatDuration(value: number | null): string {
  if (value === null) return "未完成";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

function formatToken(value: number | null): string {
  return value === null ? "未返回" : value.toLocaleString("zh-CN");
}

function statusIcon(status: AgentRunStatus) {
  if (status === "SUCCEEDED") return <CheckCircle2 className="h-4 w-4" />;
  if (status === "FAILED") return <XCircle className="h-4 w-4" />;
  if (status === "BLOCKED") return <ShieldAlert className="h-4 w-4" />;
  if (status === "ESCALATED") return <AlertTriangle className="h-4 w-4" />;
  return <Activity className="h-4 w-4" />;
}

function eventVariant(event: AgentRunEvent): "default" | "accent" | "coral" | "success" | "danger" {
  if (event.status === "FAILED") return "danger";
  if (event.status === "DENIED") return "danger";
  if (event.event_type === "MODEL_REQUEST") return "accent";
  if (event.event_type === "RUN_COMPLETED" || event.event_type === "HUMAN_ACTION") return "success";
  return "default";
}

function eventDescription(event: AgentRunEvent): string {
  const detail = event.detail;
  if (event.event_type === "MODEL_REQUEST") {
    const usage = detail.usage as { input_tokens?: number; output_tokens?: number } | undefined;
    if (usage?.input_tokens !== undefined || usage?.output_tokens !== undefined) {
      return `输入 ${usage.input_tokens ?? 0}，输出 ${usage.output_tokens ?? 0} Token`;
    }
    if (detail.error_code) return `错误代码：${String(detail.error_code)}`;
  }
  if (event.event_type === "TOOL_EXECUTION" && detail.error_code) {
    return `错误代码：${String(detail.error_code)}`;
  }
  if (event.event_type === "RUN_COMPLETED" && detail.duration_ms !== undefined) {
    return `总耗时 ${formatDuration(Number(detail.duration_ms))}`;
  }
  return "已记录运行节点";
}

function Metric({ label, value, hint, icon }: { label: string; value: string; hint: string; icon: ReactNode }) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-3 p-4">
        <div>
          <p className="text-xs text-ink-muted">{label}</p>
          <p className="mt-2 font-display text-2xl font-semibold text-ink">{value}</p>
          <p className="mt-1 text-xs text-ink-faint">{hint}</p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent/10 text-accent">
          {icon}
        </div>
      </CardContent>
    </Card>
  );
}

function RunRow({ run, selected, onSelect }: { run: AgentRunListItem; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full border-b border-border p-4 text-left transition-colors last:border-b-0 hover:bg-white/[0.03] ${
        selected ? "bg-accent/[0.07]" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/[0.05] text-ink-muted">
            <Bot className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-ink">{run.input_preview || "空输入"}</p>
            <p className="mt-1 truncate text-xs text-ink-faint">
              {run.user?.username ?? "未知用户"} · {INTENT_LABEL[run.current_intent] ?? (run.current_intent || "未识别")}
            </p>
          </div>
        </div>
        <Badge variant={STATUS_VARIANT[run.status]} className="shrink-0">
          {statusIcon(run.status)}
          {run.status_label}
        </Badge>
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-faint">
        <span>{formatDateTime(run.started_at)}</span>
        <span>{run.tool_call_count} 次工具</span>
        <span>{formatDuration(run.duration_ms)}</span>
        <span>{formatToken(run.total_tokens)} Token</span>
      </div>
    </button>
  );
}

function RunDetail({ run }: { run: AgentRunDetail }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="font-display text-lg font-semibold text-ink">运行详情</h2>
            <Badge variant={STATUS_VARIANT[run.status]}>{run.status_label}</Badge>
          </div>
          <p className="mt-1 break-all font-mono text-[11px] text-ink-faint">{run.id}</p>
        </div>
        <p className="text-xs text-ink-muted">{formatDateTime(run.started_at)}</p>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm sm:grid-cols-4">
        <div><dt className="text-xs text-ink-faint">模型</dt><dd className="mt-1 truncate text-ink">{run.model_name || "未记录"}</dd></div>
        <div><dt className="text-xs text-ink-faint">耗时</dt><dd className="mt-1 text-ink">{formatDuration(run.duration_ms)}</dd></div>
        <div><dt className="text-xs text-ink-faint">工具调用</dt><dd className="mt-1 text-ink">{run.tool_call_count} 次</dd></div>
        <div><dt className="text-xs text-ink-faint">Token</dt><dd className="mt-1 text-ink">{formatToken(run.total_tokens)}</dd></div>
      </dl>

      {run.failure_message && (
        <div className="border-l-2 border-danger bg-danger/5 px-3 py-2 text-sm text-danger">
          {run.failure_code ? `${run.failure_code}：` : ""}{run.failure_message}
        </div>
      )}

      <section>
        <h3 className="flex items-center gap-2 text-sm font-medium text-ink"><UserRound className="h-4 w-4 text-coral" /> 用户输入</h3>
        <p className="mt-2 whitespace-pre-wrap rounded-md border border-border bg-bg p-3 text-sm leading-6 text-ink-muted">{run.input_message}</p>
      </section>

      <section>
        <h3 className="flex items-center gap-2 text-sm font-medium text-ink"><Bot className="h-4 w-4 text-accent" /> Agent 回复</h3>
        <p className="mt-2 whitespace-pre-wrap rounded-md border border-border bg-bg p-3 text-sm leading-6 text-ink-muted">{run.assistant_message || "暂无回复"}</p>
      </section>

      <section>
        <h3 className="flex items-center gap-2 text-sm font-medium text-ink"><GitBranch className="h-4 w-4 text-accent" /> 执行时间线</h3>
        <ol className="mt-3 space-y-3 border-l border-border pl-4">
          {run.events.map((event) => (
            <li key={event.id} className="relative">
              <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-bg bg-accent" />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge variant={eventVariant(event)}>{event.name}</Badge>
                  <span className="text-xs text-ink-faint">第 {event.sequence} 步</span>
                </div>
                <span className="text-xs text-ink-faint">{formatDateTime(event.created_at)}</span>
              </div>
              <p className="mt-1 text-xs text-ink-muted">{eventDescription(event)}</p>
            </li>
          ))}
        </ol>
      </section>

      {run.tool_executions.length > 0 && (
        <section>
          <h3 className="flex items-center gap-2 text-sm font-medium text-ink"><Filter className="h-4 w-4 text-accent" /> 工具调用明细</h3>
          <div className="mt-3 divide-y divide-border border-y border-border">
            {run.tool_executions.map((execution) => (
              <div key={execution.id} className="py-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-ink">{execution.tool_name}</span>
                  <Badge variant={execution.status === "SUCCEEDED" ? "success" : execution.status === "DENIED" ? "danger" : "coral"}>
                    {execution.status === "SUCCEEDED" ? "成功" : execution.status === "DENIED" ? "已拒绝" : "失败"}
                  </Badge>
                </div>
                <div className="mt-2 grid gap-1 text-xs text-ink-faint sm:grid-cols-3">
                  <span>角色：{execution.agent_role}</span>
                  <span>类型：{execution.action_kind === "WRITE" ? "写操作" : "只读"}</span>
                  <span>耗时：{formatDuration(execution.duration_ms)}</span>
                </div>
                {execution.error_code && <p className="mt-1 text-xs text-danger">错误：{execution.error_code}</p>}
                <details className="mt-2 text-xs text-ink-faint">
                  <summary className="cursor-pointer hover:text-ink-muted">查看脱敏参数与结果</summary>
                  <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap rounded-md bg-bg p-2 font-mono text-[11px] leading-5 text-ink-muted">
                    {JSON.stringify({ arguments: execution.sanitized_arguments, result: execution.result }, null, 2)}
                  </pre>
                </details>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export function StaffAgentObservability() {
  const { isAuthenticated, user } = useAuth();
  const [status, setStatus] = useState<AgentRunStatus | "">("");
  const [intent, setIntent] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const filters = useMemo<AgentRunFilters>(
    () => ({ ...(status ? { status } : {}), ...(intent ? { intent } : {}), ...(search ? { search } : {}) }),
    [intent, search, status],
  );
  const runsQuery = useQuery({
    queryKey: ["staff-agent-runs", filters],
    queryFn: () => afterSalesApi.listStaffAgentRuns(filters),
    enabled: isAuthenticated && Boolean(user?.is_staff),
    refetchInterval: 30_000,
  });
  const detailQuery = useQuery({
    queryKey: ["staff-agent-run", selectedRunId],
    queryFn: () => afterSalesApi.getStaffAgentRun(selectedRunId!),
    enabled: Boolean(selectedRunId) && isAuthenticated && Boolean(user?.is_staff),
  });

  const data = runsQuery.data;
  const selectedRunIdToUse = selectedRunId && data?.runs.some((run) => run.id === selectedRunId) ? selectedRunId : null;
  useEffect(() => {
    if (data?.runs.length && selectedRunId === null) {
      setSelectedRunId(data.runs[0].id);
    }
    if (selectedRunId && data && !data.runs.some((run) => run.id === selectedRunId)) {
      setSelectedRunId(data.runs[0]?.id ?? null);
    }
  }, [data, selectedRunId]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user?.is_staff) return <Navigate to="/" replace />;

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSearch(searchDraft.trim());
  };

  return (
    <Container className="py-6 sm:py-8">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-accent/15 text-accent"><BarChart3 className="h-5 w-5" /></div>
          <div><h1 className="font-display text-2xl font-semibold text-ink">Agent 观测</h1><p className="text-sm text-ink-muted">仅管理员可见 · 最近 100 次运行</p></div>
        </div>
        <Button variant="outline" size="icon" onClick={() => void runsQuery.refetch()} isLoading={runsQuery.isFetching} aria-label="刷新 Agent 运行记录" title="刷新 Agent 运行记录">
          {!runsQuery.isFetching && <RefreshCw className="h-4 w-4" />}
        </Button>
      </div>

      {data && (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="运行次数" value={String(data.summary.total_runs)} hint={`完成率 ${data.summary.success_rate}%`} icon={<Activity className="h-4 w-4" />} />
          <Metric label="平均耗时" value={formatDuration(data.summary.average_duration_ms)} hint="已完成的请求范围" icon={<Clock3 className="h-4 w-4" />} />
          <Metric label="工具调用" value={String(data.summary.total_tool_calls)} hint={`失败 ${data.summary.failed_tool_calls} · 拒绝 ${data.summary.denied_tool_calls}`} icon={<Filter className="h-4 w-4" />} />
          <Metric label="Token 用量" value={formatToken(data.summary.total_tokens)} hint={`失败运行 ${data.summary.failed_runs} 次`} icon={<Bot className="h-4 w-4" />} />
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select value={status} onChange={(event) => setStatus(event.target.value as AgentRunStatus | "")} className="h-10 rounded-md border border-border-strong bg-bg-surface px-3 text-sm text-ink outline-none focus:border-accent" aria-label="运行状态筛选">
          {STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <select value={intent} onChange={(event) => setIntent(event.target.value)} className="h-10 rounded-md border border-border-strong bg-bg-surface px-3 text-sm text-ink outline-none focus:border-accent" aria-label="意图筛选">
          {INTENT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <form onSubmit={submitSearch} className="flex min-w-[220px] flex-1 items-center gap-2 sm:max-w-md">
          <div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" /><input value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} placeholder="搜索用户、输入或响应 ID" className="h-10 w-full rounded-md border border-border-strong bg-bg-surface pl-9 pr-3 text-sm text-ink outline-none placeholder:text-ink-faint focus:border-accent" /></div>
          <Button type="submit" variant="secondary" size="sm"><Search className="h-4 w-4" />筛选</Button>
        </form>
      </div>

      {runsQuery.isLoading ? <div className="flex min-h-[40vh] items-center justify-center"><Spinner /></div> : runsQuery.isError ? <EmptyState icon={AlertTriangle} title="运行记录加载失败" description={getErrorMessage(runsQuery.error, "请刷新页面后重试。 ")} actionLabel="重新加载" onAction={() => void runsQuery.refetch()} /> : !data?.runs.length ? <EmptyState icon={Eye} title="暂无 Agent 运行记录" description="用户使用售后助手后，运行轨迹会显示在这里。" /> : (
        <div className="grid min-h-[620px] gap-4 lg:grid-cols-[minmax(320px,0.85fr)_minmax(0,1.5fr)]">
          <Card className="overflow-hidden"><div className="border-b border-border px-4 py-3"><h2 className="text-sm font-semibold text-ink">运行列表</h2><p className="mt-1 text-xs text-ink-faint">共 {data.runs.length} 条</p></div><div>{data.runs.map((run) => <RunRow key={run.id} run={run} selected={run.id === selectedRunIdToUse} onSelect={() => setSelectedRunId(run.id)} />)}</div></Card>
          <Card><CardContent className="p-5">{detailQuery.isLoading ? <div className="flex min-h-[500px] items-center justify-center"><Spinner /></div> : detailQuery.isError ? <EmptyState icon={AlertTriangle} title="详情加载失败" description={getErrorMessage(detailQuery.error, "请重新选择一条运行记录。 ")} /> : detailQuery.data ? <RunDetail run={detailQuery.data} /> : <div className="flex min-h-[500px] items-center justify-center text-sm text-ink-muted">请选择一条运行记录。</div>}</CardContent></Card>
        </div>
      )}
    </Container>
  );
}
