"""Persistent domain models for the after-sales Agent workflow."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from pgvector.django import HnswIndex, VectorField

from core.mixins import TimeStampedMixin, UUIDPrimaryKeyMixin


def generate_case_number() -> str:
    """Create a short, non-sequential identifier safe to show to customers."""

    return f"AS-{uuid.uuid4().hex[:12].upper()}"


class AgentConversation(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """A persisted customer conversation and its workflow state."""

    class State(models.TextChoices):
        ACTIVE = "ACTIVE", "处理中"
        AWAITING_DETAILS = "AWAITING_DETAILS", "等待补充信息"
        AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION", "等待用户确认"
        ESCALATED = "ESCALATED", "已转人工"
        RESOLVED = "RESOLVED", "已解决"
        FAILED = "FAILED", "处理失败"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    state = models.CharField("会话状态", max_length=32, choices=State.choices, default=State.ACTIVE)
    current_intent = models.CharField("当前意图", max_length=64, blank=True)
    summary = models.TextField("会话摘要", blank=True)
    selected_order = models.ForeignKey(
        "cart_orders.Order",
        verbose_name="当前订单",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_conversations",
    )
    tool_failure_count = models.PositiveSmallIntegerField("连续工具失败次数", default=0)
    context = models.JSONField("会话上下文", default=dict, blank=True)
    last_active_at = models.DateTimeField("最后活跃时间", default=timezone.now)

    class Meta:
        verbose_name = "Agent 会话"
        verbose_name_plural = "Agent 会话"
        ordering = ("-last_active_at",)
        indexes = [
            models.Index(fields=["user", "state"]),
            models.Index(fields=["state", "last_active_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} 的会话 {str(self.id)[:8]}"


class AgentMessage(TimeStampedMixin):
    """An immutable user, assistant, system, or tool message in a conversation."""

    class Role(models.TextChoices):
        USER = "USER", "用户"
        ASSISTANT = "ASSISTANT", "助手"
        TOOL = "TOOL", "工具"
        SYSTEM = "SYSTEM", "系统"

    conversation = models.ForeignKey(
        AgentConversation,
        verbose_name="会话",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField("角色", max_length=16, choices=Role.choices)
    content = models.TextField("消息内容", blank=True)
    tool_name = models.CharField("工具名称", max_length=100, blank=True)
    tool_call_id = models.UUIDField("工具调用标识", null=True, blank=True)
    tool_arguments = models.JSONField("脱敏工具参数", default=dict, blank=True)
    tool_result = models.JSONField("工具结果", default=dict, blank=True)

    class Meta:
        verbose_name = "Agent 消息"
        verbose_name_plural = "Agent 消息"
        ordering = ("created_at",)
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self) -> str:
        return f"{self.get_role_display()}：{self.content[:40]}"


class ConfirmationRequest(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """A short-lived, idempotent approval required before a sensitive action."""

    class ActionType(models.TextChoices):
        REFUND_REQUEST = "REFUND_REQUEST", "提交退款申请"
        RETURN_REFUND_REQUEST = "RETURN_REFUND_REQUEST", "提交退货退款申请"
        CANCEL_ORDER = "CANCEL_ORDER", "取消待支付订单"
        HUMAN_TICKET = "HUMAN_TICKET", "提交人工服务工单"

    class Status(models.TextChoices):
        PENDING = "PENDING", "待确认"
        CONFIRMED = "CONFIRMED", "已确认"
        REJECTED = "REJECTED", "已拒绝"
        EXPIRED = "EXPIRED", "已过期"
        EXECUTED = "EXECUTED", "已执行"
        FAILED = "FAILED", "执行失败"

    conversation = models.ForeignKey(
        AgentConversation,
        verbose_name="会话",
        on_delete=models.CASCADE,
        related_name="confirmation_requests",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="confirmation_requests",
    )
    order = models.ForeignKey(
        "cart_orders.Order",
        verbose_name="订单",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="confirmation_requests",
    )
    action_type = models.CharField("操作类型", max_length=32, choices=ActionType.choices)
    status = models.CharField("确认状态", max_length=16, choices=Status.choices, default=Status.PENDING)
    payload = models.JSONField("待执行参数", default=dict)
    result = models.JSONField("执行结果", default=dict, blank=True)
    idempotency_key = models.UUIDField("幂等键", default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField("过期时间")
    confirmed_at = models.DateTimeField("确认时间", null=True, blank=True)
    executed_at = models.DateTimeField("执行时间", null=True, blank=True)

    class Meta:
        verbose_name = "确认请求"
        verbose_name_plural = "确认请求"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    @property
    def is_expired(self) -> bool:
        return self.status == self.Status.PENDING and self.expires_at <= timezone.now()

    def __str__(self) -> str:
        return f"{self.get_action_type_display()} ({self.get_status_display()})"


class AfterSalesCase(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """A customer-facing after-sales ticket that is reviewed by staff."""

    class CaseType(models.TextChoices):
        REFUND = "REFUND", "退款申请"
        RETURN_REFUND = "RETURN_REFUND", "退货退款申请"
        QUALITY_ISSUE = "QUALITY_ISSUE", "质量问题"
        DELIVERY_ISSUE = "DELIVERY_ISSUE", "物流异常"
        ORDER_VERIFICATION = "ORDER_VERIFICATION", "订单核验"
        HUMAN_SERVICE = "HUMAN_SERVICE", "人工服务"
        SYSTEM_EXCEPTION = "SYSTEM_EXCEPTION", "系统异常"

    class Status(models.TextChoices):
        PENDING_REVIEW = "PENDING_REVIEW", "待人工审核"
        IN_REVIEW = "IN_REVIEW", "审核中"
        NEED_CUSTOMER_INFO = "NEED_CUSTOMER_INFO", "待用户补充"
        APPROVED = "APPROVED", "已通过"
        REJECTED = "REJECTED", "已拒绝"
        CLOSED = "CLOSED", "已关闭"
        CANCELLED = "CANCELLED", "用户取消"

    class Priority(models.TextChoices):
        LOW = "LOW", "低"
        NORMAL = "NORMAL", "普通"
        HIGH = "HIGH", "高"
        URGENT = "URGENT", "紧急"

    case_number = models.CharField(
        "工单编号", max_length=20, unique=True, default=generate_case_number, editable=False
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.PROTECT,
        related_name="after_sales_cases",
    )
    order = models.ForeignKey(
        "cart_orders.Order",
        verbose_name="关联订单",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="after_sales_cases",
    )
    conversation = models.ForeignKey(
        AgentConversation,
        verbose_name="来源会话",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="after_sales_cases",
    )
    confirmation_request = models.OneToOneField(
        ConfirmationRequest,
        verbose_name="确认请求",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="after_sales_case",
    )
    case_type = models.CharField("工单类型", max_length=32, choices=CaseType.choices)
    status = models.CharField(
        "工单状态", max_length=24, choices=Status.choices, default=Status.PENDING_REVIEW
    )
    priority = models.CharField(
        "优先级", max_length=16, choices=Priority.choices, default=Priority.NORMAL
    )
    reason = models.TextField("用户原因")
    agent_summary = models.TextField("Agent 摘要", blank=True)
    staff_note = models.TextField("客服备注", blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="处理人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_after_sales_cases",
        limit_choices_to={"is_staff": True},
    )
    resolved_at = models.DateTimeField("处理完成时间", null=True, blank=True)

    class Meta:
        verbose_name = "售后工单"
        verbose_name_plural = "售后工单"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["order", "case_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.case_number} - {self.get_case_type_display()}"


class CustomerMemory(TimeStampedMixin):
    """Small, structured memories used to personalize later conversations."""

    class MemoryType(models.TextChoices):
        PREFERENCE = "PREFERENCE", "偏好"
        CASE_SUMMARY = "CASE_SUMMARY", "售后摘要"
        CONVERSATION_SUMMARY = "CONVERSATION_SUMMARY", "会话摘要"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="customer_memories",
    )
    source_conversation = models.ForeignKey(
        AgentConversation,
        verbose_name="来源会话",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memories",
    )
    memory_type = models.CharField("记忆类型", max_length=32, choices=MemoryType.choices)
    key = models.CharField("记忆键", max_length=100)
    value = models.JSONField("记忆内容", default=dict)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "用户记忆"
        verbose_name_plural = "用户记忆"
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "memory_type", "key"], name="after_sales_unique_customer_memory"
            )
        ]
        indexes = [models.Index(fields=["user", "memory_type", "is_active"])]

    def __str__(self) -> str:
        return f"{self.user} - {self.get_memory_type_display()}：{self.key}"


class KnowledgeDocument(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """Trusted, staff-maintained source documents for after-sales answers."""

    title = models.CharField("标题", max_length=160)
    slug = models.SlugField("稳定标识", max_length=100, unique=True)
    category = models.CharField("分类", max_length=64)
    source_label = models.CharField("引用名称", max_length=160)
    content = models.TextField("知识内容")
    is_published = models.BooleanField("允许 Agent 检索", default=True)

    class Meta:
        verbose_name = "售后知识文档"
        verbose_name_plural = "售后知识文档"
        ordering = ("category", "title")

    def __str__(self) -> str:
        return self.title


class KnowledgeChunk(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """One embedded, citation-ready chunk from a trusted knowledge document."""

    document = models.ForeignKey(
        KnowledgeDocument,
        verbose_name="所属文档",
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    sequence = models.PositiveSmallIntegerField("切片序号")
    content = models.TextField("切片内容")
    content_hash = models.CharField("内容哈希", max_length=64)
    embedding = VectorField("向量", dimensions=1536, null=True, blank=True)

    class Meta:
        verbose_name = "售后知识切片"
        verbose_name_plural = "售后知识切片"
        ordering = ("document", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("document", "sequence"), name="after_sales_unique_knowledge_chunk"
            )
        ]
        indexes = [
            models.Index(fields=("document", "sequence"), name="after_sales_documen_6ba5ae_idx"),
            HnswIndex(
                name="as_knowledge_emb_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.document.title} #{self.sequence}"


class ToolExecution(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """Append-only audit data for every registered Agent tool invocation."""

    class ActionKind(models.TextChoices):
        READ = "READ", "只读"
        WRITE = "WRITE", "写操作"

    class Status(models.TextChoices):
        PENDING = "PENDING", "执行中"
        SUCCEEDED = "SUCCEEDED", "成功"
        FAILED = "FAILED", "失败"
        DENIED = "DENIED", "已拒绝"

    class Initiator(models.TextChoices):
        AGENT = "AGENT", "Agent"
        SYSTEM = "SYSTEM", "系统"
        HUMAN = "HUMAN", "人工"

    conversation = models.ForeignKey(
        AgentConversation,
        verbose_name="会话",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tool_executions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tool_executions",
    )
    after_sales_case = models.ForeignKey(
        AfterSalesCase,
        verbose_name="售后工单",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tool_executions",
    )
    confirmation_request = models.ForeignKey(
        ConfirmationRequest,
        verbose_name="确认请求",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tool_executions",
    )
    agent_role = models.CharField("执行 Agent", max_length=32, default="coordinator")
    tool_name = models.CharField("工具名称", max_length=100)
    action_kind = models.CharField("操作类型", max_length=8, choices=ActionKind.choices)
    status = models.CharField("执行状态", max_length=16, choices=Status.choices, default=Status.PENDING)
    initiated_by = models.CharField(
        "发起方", max_length=16, choices=Initiator.choices, default=Initiator.AGENT
    )
    sanitized_arguments = models.JSONField("脱敏参数", default=dict, blank=True)
    result = models.JSONField("执行结果", default=dict, blank=True)
    error_code = models.CharField("错误代码", max_length=100, blank=True)
    duration_ms = models.PositiveIntegerField("耗时（毫秒）", null=True, blank=True)

    class Meta:
        verbose_name = "工具执行审计"
        verbose_name_plural = "工具执行审计"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["tool_name", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.tool_name} - {self.get_status_display()}"
