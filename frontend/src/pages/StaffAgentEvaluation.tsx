import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Play,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Navigate } from "react-router-dom";
import { afterSalesApi } from "@/api/afterSales";
import { getErrorMessage } from "@/api/client";
import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Container } from "@/components/ui/Container";
import { Spinner } from "@/components/ui/Skeleton";
import { useAuth } from "@/hooks/useAuth";
import type {
  AgentEvaluationCaseResult,
  AgentEvaluationMetric,
  AgentEvaluationRunDetail,
} from "@/types";
import { formatDateTime } from "@/utils/format";

const METRIC_CONFIG: Array<{
  key: string;
  label: string;
  icon: ReactNode;
  tone: "accent" | "success" | "coral" | "danger";
}> = [
  { key: "intent_recognition", label: "意图识别准确率", icon: <ClipboardCheck className="h-4 w-4" />, tone: "accent" },
  { key: "tool_selection", label: "工具选择准确率", icon: <BarChart3 className="h-4 w-4" />, tone: "accent" },
  { key: "parameter_correctness", label: "参数正确率", icon: <CheckCircle2 className="h-4 w-4" />, tone: "success" },
  { key: "unauthorized_interception", label: "越权拦截率", icon: <ShieldCheck className="h-4 w-4" />, tone: "success" },
  { key: "dangerous_interception", label: "危险操作拦截率", icon: <ShieldCheck className="h-4 w-4" />, tone: "danger" },
  { key: "average_response_time", label: "平均响应时间", icon: <Clock3 className="h-4 w-4" />, tone: "coral" },
  { key: "human_handoff", label: "人工转接率", icon: <AlertTriangle className="h-4 w-4" />, tone: "coral" },
  { key: "failure", label: "失败率", icon: <XCircle className="h-4 w-4" />, tone: "danger" },
];

const INTENT_LABEL: Record<string, string> = {
  ORDER_QUERY: "订单查询",
  REFUND: "退款",
  RETURN_REFUND: "退货退款",
  CANCEL_ORDER: "取消订单",
  QUALITY_ISSUE: "质量问题",
  DELIVERY_ISSUE: "物流问题",
  CASE_QUERY: "工单查询",
  KNOWLEDGE_QUERY: "知识问答",
  GENERAL: "其他",
};

const toneClasses = {
  accent: "bg-accent/10 text-accent",
  success: "bg-success/10 text-success",
  coral: "bg-coral/10 text-coral",
  danger: "bg-danger/10 text-danger",
};

function formatMetric(metric: AgentEvaluationMetric | undefined): string {
  if (!metric) return "暂无";
  if (metric.value !== undefined) return `${metric.value} ${metric.unit ?? ""}`.trim();
  return `${metric.rate ?? 0}%`;
}

function metricHint(metric: AgentEvaluationMetric | undefined): string {
  if (!metric || metric.value !== undefined) return "20 条确定性回放案例";
  if (metric.passed === undefined) return `失败 ${metric.failed ?? 0} / ${metric.total ?? 0} 条`;
  return `${metric.passed ?? 0} / ${metric.total ?? 0} 条通过`;
}

function ResultBadge({ passed, pending = false }: { passed: boolean | null; pending?: boolean }) {
  if (pending) return <Badge variant="outline">不适用</Badge>;
  return passed ? (
    <Badge variant="success"><CheckCircle2 className="h-3 w-3" />通过</Badge>
  ) : (
    <Badge variant="danger"><XCircle className="h-3 w-3" />失败</Badge>
  );
}

function MetricCard({
  label,
  metric,
  icon,
  tone,
}: {
  label: string;
  metric: AgentEvaluationMetric | undefined;
  icon: ReactNode;
  tone: keyof typeof toneClasses;
}) {
  const percentage = metric?.rate ?? 0;
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs text-ink-muted">{label}</p>
            <p className="mt-2 font-display text-2xl font-semibold text-ink">{formatMetric(metric)}</p>
            <p className="mt-1 text-xs text-ink-faint">{metricHint(metric)}</p>
          </div>
          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${toneClasses[tone]}`}>
            {icon}
          </div>
        </div>
        {metric?.value === undefined && (
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
            <div className={`h-full rounded-full ${tone === "danger" ? "bg-danger" : tone === "success" ? "bg-success" : tone === "coral" ? "bg-coral" : "bg-accent"}`} style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function toolsText(tools: string[]): string {
  return tools.length ? tools.join(" → ") : "无工具";
}

function CaseResultRow({ result }: { result: AgentEvaluationCaseResult }) {
  const securityPassed = result.unauthorized_case ? result.unauthorized_blocked : result.dangerous_case ? result.dangerous_blocked : result.authorization_passed;
  return (
    <tr className="border-b border-border align-top last:border-b-0">
      <td className="whitespace-nowrap px-3 py-3">
        <p className="font-mono text-xs text-ink">{result.case_id}</p>
        <p className="mt-1 text-xs text-ink-faint">{result.category}</p>
      </td>
      <td className="min-w-[220px] max-w-[300px] px-3 py-3 text-sm text-ink-muted">{result.description}<p className="mt-1 text-xs text-ink-faint">{result.message}</p></td>
      <td className="whitespace-nowrap px-3 py-3 text-xs"><span className="text-ink-faint">期望：</span>{INTENT_LABEL[result.expected_intent] ?? result.expected_intent}<br /><span className="text-ink-faint">实际：</span>{(INTENT_LABEL[result.actual_intent] ?? result.actual_intent) || "未识别"}<div className="mt-2"><ResultBadge passed={result.intent_passed} /></div></td>
      <td className="min-w-[210px] px-3 py-3"><p className="font-mono text-[11px] leading-5 text-ink-muted">{toolsText(result.actual_tools)}</p><p className="mt-1 text-[11px] text-ink-faint">期望：{toolsText(result.expected_tools)}</p><div className="mt-2"><ResultBadge passed={result.tool_selection_passed} /></div></td>
      <td className="whitespace-nowrap px-3 py-3"><ResultBadge passed={result.parameter_passed} pending={!result.parameter_applicable} /></td>
      <td className="whitespace-nowrap px-3 py-3"><ResultBadge passed={securityPassed} /></td>
      <td className="whitespace-nowrap px-3 py-3"><ResultBadge passed={result.response_compliance_passed} /></td>
      <td className="whitespace-nowrap px-3 py-3 text-xs text-ink-faint">{result.response_time_ms} ms{result.human_escalated && <span className="mt-1 block text-coral">已转人工</span>}{result.failures.length > 0 && <details className="mt-2 max-w-[180px] whitespace-normal text-danger"><summary className="cursor-pointer">查看失败原因</summary><ul className="mt-1 list-disc pl-4">{result.failures.map((failure) => <li key={failure}>{failure}</li>)}</ul></details>}</td>
    </tr>
  );
}

function EvaluationDetail({ evaluation }: { evaluation: AgentEvaluationRunDetail }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2"><h2 className="font-display text-lg font-semibold text-ink">评测结果</h2><Badge variant={evaluation.failed_cases ? "coral" : "success"}>{evaluation.failed_cases ? `${evaluation.failed_cases} 条失败` : "全部通过"}</Badge></div>
          <p className="mt-1 font-mono text-[11px] text-ink-faint">批次 {evaluation.id}</p>
        </div>
        <div className="text-right text-xs text-ink-muted"><p>{formatDateTime(evaluation.started_at)}</p><p className="mt-1">{evaluation.passed_cases} / {evaluation.total_cases} 通过</p></div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {METRIC_CONFIG.map((config) => <MetricCard key={config.key} label={config.label} metric={evaluation.metrics[config.key]} icon={config.icon} tone={config.tone} />)}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="text-sm font-semibold text-ink">案例明细</h3><p className="mt-1 text-xs text-ink-faint">每条案例分别校验意图、工具、参数、权限安全与回复合规。</p></div><div className="text-xs text-ink-faint">模式：{evaluation.mode} · 触发：{evaluation.trigger_label}</div></div>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="min-w-[1150px] w-full border-collapse text-left">
          <thead className="bg-bg-elevated text-xs text-ink-muted"><tr><th className="px-3 py-3 font-medium">案例</th><th className="px-3 py-3 font-medium">场景</th><th className="px-3 py-3 font-medium">意图</th><th className="px-3 py-3 font-medium">工具选择</th><th className="px-3 py-3 font-medium">参数</th><th className="px-3 py-3 font-medium">权限 / 安全</th><th className="px-3 py-3 font-medium">回复</th><th className="px-3 py-3 font-medium">耗时</th></tr></thead>
          <tbody>{evaluation.cases.map((result) => <CaseResultRow key={result.id} result={result} />)}</tbody>
        </table>
      </div>
    </div>
  );
}

export function StaffAgentEvaluation() {
  const { isAuthenticated, user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const listQuery = useQuery({
    queryKey: ["staff-agent-evaluations"],
    queryFn: afterSalesApi.listStaffAgentEvaluations,
    enabled: isAuthenticated && Boolean(user?.is_staff),
  });
  const detailQuery = useQuery({
    queryKey: ["staff-agent-evaluation", selectedRunId],
    queryFn: () => afterSalesApi.getStaffAgentEvaluation(selectedRunId!),
    enabled: Boolean(selectedRunId) && isAuthenticated && Boolean(user?.is_staff),
  });
  const runMutation = useMutation({
    mutationFn: afterSalesApi.runStaffAgentEvaluation,
    onSuccess: async (evaluation) => {
      setSelectedRunId(evaluation.id);
      await queryClient.invalidateQueries({ queryKey: ["staff-agent-evaluations"] });
    },
  });
  const data = listQuery.data;
  useEffect(() => {
    if (data?.runs.length && (!selectedRunId || !data.runs.some((run) => run.id === selectedRunId))) {
      setSelectedRunId(data.runs[0].id);
    }
  }, [data, selectedRunId]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user?.is_staff) return <Navigate to="/" replace />;

  return (
    <Container className="py-6 sm:py-8">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-md bg-success/15 text-success"><ClipboardCheck className="h-5 w-5" /></div><div><h1 className="font-display text-2xl font-semibold text-ink">Agent 评测</h1><p className="text-sm text-ink-muted">仅管理员可见 · 评估 Agent 的可靠性与安全边界</p></div></div>
        <div className="flex items-center gap-2"><Button variant="outline" size="icon" onClick={() => void listQuery.refetch()} isLoading={listQuery.isFetching} aria-label="刷新评测批次" title="刷新评测批次">{!listQuery.isFetching && <RefreshCw className="h-4 w-4" />}</Button><Button onClick={() => runMutation.mutate()} isLoading={runMutation.isPending}><Play className="h-4 w-4" />运行评测</Button></div>
      </div>
      <div className="mb-5 border-l-2 border-accent bg-accent/5 px-3 py-2 text-sm text-ink-muted">评测使用固定模型回放，不调用真实 OpenAI，不消耗额度；临时用户、订单、会话和工单会自动回滚，只保存指标与案例结果。</div>
      {runMutation.isError && <div className="mb-4 border-l-2 border-danger bg-danger/5 px-3 py-2 text-sm text-danger">评测运行失败：{getErrorMessage(runMutation.error, "请稍后重试。")}</div>}
      {listQuery.isLoading ? <div className="flex min-h-[40vh] items-center justify-center"><Spinner /></div> : listQuery.isError ? <EmptyState icon={AlertTriangle} title="评测批次加载失败" description={getErrorMessage(listQuery.error, "请刷新页面后重试。")} actionLabel="重新加载" onAction={() => void listQuery.refetch()} /> : !data?.runs.length ? <EmptyState icon={ClipboardCheck} title="还没有评测记录" description="点击右上角运行评测，生成第一批 20 条案例结果。" actionLabel="运行评测" onAction={() => runMutation.mutate()} /> : <>
        <div className="mb-4 flex gap-2 overflow-x-auto pb-1">{data.runs.map((run) => <button key={run.id} type="button" onClick={() => setSelectedRunId(run.id)} className={`min-w-[190px] rounded-md border px-3 py-2 text-left transition-colors ${selectedRunId === run.id ? "border-accent bg-accent/10" : "border-border bg-bg-surface hover:border-border-strong"}`}><div className="flex items-center justify-between gap-2"><span className="text-xs font-medium text-ink">{formatDateTime(run.started_at)}</span><Badge variant={run.failed_cases ? "coral" : "success"}>{run.passed_cases}/{run.total_cases}</Badge></div><p className="mt-1 text-[11px] text-ink-faint">{run.trigger_label} · 平均 {run.average_response_ms} ms</p></button>)}</div>
        {detailQuery.isLoading ? <div className="flex min-h-[400px] items-center justify-center"><Spinner /></div> : detailQuery.isError ? <EmptyState icon={AlertTriangle} title="评测详情加载失败" description={getErrorMessage(detailQuery.error, "请重新选择批次。")} /> : detailQuery.data ? <EvaluationDetail evaluation={detailQuery.data} /> : <div className="py-20 text-center text-sm text-ink-muted">请选择一个评测批次。</div>}
      </>}
    </Container>
  );
}
