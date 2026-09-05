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


class AfterSalesNotification(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """An owner-scoped in-app notification emitted by a case lifecycle event."""

    class EventType(models.TextChoices):
        CASE_CREATED = "CASE_CREATED", "工单创建"
        CASE_APPROVED = "CASE_APPROVED", "审核通过"
        CASE_REJECTED = "CASE_REJECTED", "审核拒绝"
        NEED_CUSTOMER_INFO = "NEED_CUSTOMER_INFO", "要求补充资料"

    class EmailStatus(models.TextChoices):
        PENDING = "PENDING", "待发送"
        SENT = "SENT", "模拟已发送"
        SKIPPED = "SKIPPED", "无邮箱已跳过"
        FAILED = "FAILED", "发送失败"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="after_sales_notifications",
    )
    after_sales_case = models.ForeignKey(
        AfterSalesCase,
        verbose_name="售后工单",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    event_type = models.CharField("事件类型", max_length=32, choices=EventType.choices)
    title = models.CharField("标题", max_length=160)
    message = models.TextField("通知内容")
    action_url = models.CharField("跳转地址", max_length=200, default="/after-sales")
    is_read = models.BooleanField("已读", default=False)
    read_at = models.DateTimeField("阅读时间", null=True, blank=True)
    email_status = models.CharField(
        "邮件状态", max_length=16, choices=EmailStatus.choices, default=EmailStatus.PENDING
    )
    email_sent_at = models.DateTimeField("邮件模拟发送时间", null=True, blank=True)
    email_error = models.CharField("邮件错误", max_length=255, blank=True)

    class Meta:
        verbose_name = "售后站内通知"
        verbose_name_plural = "售后站内通知"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["after_sales_case", "event_type"],
                name="after_sales_unique_case_notification_event",
            )
        ]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
            models.Index(fields=["email_status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.title}"


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

    class SourceType(models.TextChoices):
        TEXT = "TEXT", "文本"
        FILE = "FILE", "文件"
        WEBPAGE = "WEBPAGE", "网页"

    class IndexStatus(models.TextChoices):
        PENDING = "PENDING", "待索引"
        PROCESSING = "PROCESSING", "索引中"
        READY = "READY", "已就绪"
        FAILED = "FAILED", "索引失败"

    title = models.CharField("标题", max_length=160)
    slug = models.SlugField("稳定标识", max_length=100, unique=True)
    category = models.CharField("分类", max_length=64)
    source_label = models.CharField("引用名称", max_length=160)
    content = models.TextField("知识内容")
    is_published = models.BooleanField("允许 Agent 检索", default=True)
    source_type = models.CharField(
        "来源类型", max_length=16, choices=SourceType.choices, default=SourceType.TEXT
    )
    file = models.FileField("原始文件", upload_to="after-sales/knowledge/", blank=True, null=True)
    source_url = models.URLField("网页地址", max_length=1000, blank=True)
    product = models.ForeignKey(
        "products.Product",
        verbose_name="适用商品",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="after_sales_knowledge_documents",
    )
    product_category = models.ForeignKey(
        "products.Category",
        verbose_name="适用商品分类",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="after_sales_knowledge_documents",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_knowledge_documents",
    )
    index_status = models.CharField(
        "索引状态", max_length=16, choices=IndexStatus.choices, default=IndexStatus.PENDING
    )
    index_error = models.CharField("索引错误", max_length=500, blank=True)
    indexed_at = models.DateTimeField("索引完成时间", null=True, blank=True)
    chunk_count = models.PositiveIntegerField("切片数量", default=0)

    class Meta:
        verbose_name = "售后知识文档"
        verbose_name_plural = "售后知识文档"
        ordering = ("category", "title")
        indexes = [
            models.Index(
                fields=("index_status", "updated_at"),
                name="after_sales_kdoc_idx",
            ),
            models.Index(
                fields=("product", "is_published"),
                name="after_sales_kprod_idx",
            ),
            models.Index(
                fields=("product_category", "is_published"),
                name="after_sales_kcat_idx",
            ),
        ]

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
    vector_id = models.CharField("向量库 ID", max_length=100, blank=True)

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


class AgentRun(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """One complete customer-facing Agent turn, kept separate from chat history."""

    class Status(models.TextChoices):
        RUNNING = "RUNNING", "执行中"
        SUCCEEDED = "SUCCEEDED", "已完成"
        AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION", "等待确认"
        ESCALATED = "ESCALATED", "已转人工"
        BLOCKED = "BLOCKED", "已拦截"
        FAILED = "FAILED", "失败"

    conversation = models.ForeignKey(
        AgentConversation,
        verbose_name="会话",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_runs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_runs",
    )
    confirmation_request = models.ForeignKey(
        ConfirmationRequest,
        verbose_name="确认请求",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_runs",
    )
    model_name = models.CharField("模型", max_length=120, blank=True)
    current_intent = models.CharField("识别意图", max_length=64, blank=True)
    input_message = models.TextField("用户输入", blank=True)
    assistant_message = models.TextField("助手回复", blank=True)
    agent_roles = models.JSONField("协作角色", default=list, blank=True)
    status = models.CharField("运行状态", max_length=32, choices=Status.choices, default=Status.RUNNING)
    failure_code = models.CharField("失败代码", max_length=100, blank=True)
    failure_message = models.CharField("失败说明", max_length=255, blank=True)
    response_id = models.CharField("模型响应 ID", max_length=120, blank=True)
    tool_rounds = models.PositiveSmallIntegerField("工具轮数", default=0)
    tool_call_count = models.PositiveSmallIntegerField("工具调用次数", default=0)
    successful_tool_count = models.PositiveSmallIntegerField("成功工具数", default=0)
    failed_tool_count = models.PositiveSmallIntegerField("失败工具数", default=0)
    denied_tool_count = models.PositiveSmallIntegerField("拒绝工具数", default=0)
    input_tokens = models.PositiveIntegerField("输入 Token", null=True, blank=True)
    output_tokens = models.PositiveIntegerField("输出 Token", null=True, blank=True)
    total_tokens = models.PositiveIntegerField("总 Token", null=True, blank=True)
    started_at = models.DateTimeField("开始时间", default=timezone.now)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    duration_ms = models.PositiveIntegerField("总耗时（毫秒）", null=True, blank=True)

    class Meta:
        verbose_name = "Agent 运行记录"
        verbose_name_plural = "Agent 运行记录"
        ordering = ("-started_at",)
        indexes = [
            models.Index(fields=["status", "started_at"]),
            models.Index(fields=["user", "started_at"]),
            models.Index(fields=["current_intent", "started_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.model_name or 'Agent'} - {self.get_status_display()} - {str(self.id)[:8]}"


class AgentRunEvent(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """Safe, structured milestones inside one Agent run."""

    class EventType(models.TextChoices):
        MODEL_REQUEST = "MODEL_REQUEST", "模型请求"
        TOOL_EXECUTION = "TOOL_EXECUTION", "工具执行"
        HUMAN_ACTION = "HUMAN_ACTION", "人工操作"
        RUN_COMPLETED = "RUN_COMPLETED", "运行结束"

    class Status(models.TextChoices):
        SUCCEEDED = "SUCCEEDED", "成功"
        FAILED = "FAILED", "失败"
        DENIED = "DENIED", "已拒绝"
        INFO = "INFO", "信息"

    run = models.ForeignKey(
        AgentRun,
        verbose_name="Agent 运行记录",
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField("事件类型", max_length=32, choices=EventType.choices)
    status = models.CharField("事件状态", max_length=16, choices=Status.choices)
    sequence = models.PositiveSmallIntegerField("顺序")
    name = models.CharField("事件名称", max_length=120)
    detail = models.JSONField("事件详情", default=dict, blank=True)
    duration_ms = models.PositiveIntegerField("耗时（毫秒）", null=True, blank=True)

    class Meta:
        verbose_name = "Agent 运行事件"
        verbose_name_plural = "Agent 运行事件"
        ordering = ("sequence", "created_at")
        indexes = [
            models.Index(fields=["run", "sequence"]),
            models.Index(fields=["event_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.run_id} - {self.name}"


class AgentEvaluationRun(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """One persisted deterministic evaluation batch for the staff dashboard."""

    class Status(models.TextChoices):
        RUNNING = "RUNNING", "执行中"
        SUCCEEDED = "SUCCEEDED", "已完成"
        FAILED = "FAILED", "失败"

    class Trigger(models.TextChoices):
        DASHBOARD = "DASHBOARD", "后台工作台"
        COMMAND = "COMMAND", "管理命令"

    status = models.CharField("评测状态", max_length=16, choices=Status.choices, default=Status.RUNNING)
    trigger = models.CharField("触发方式", max_length=16, choices=Trigger.choices, default=Trigger.DASHBOARD)
    mode = models.CharField("评测模式", max_length=64, default="deterministic_replay")
    started_at = models.DateTimeField("开始时间", default=timezone.now)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    total_cases = models.PositiveIntegerField("案例总数", default=0)
    passed_cases = models.PositiveIntegerField("通过案例数", default=0)
    failed_cases = models.PositiveIntegerField("失败案例数", default=0)
    intent_correct = models.PositiveIntegerField("意图正确数", default=0)
    intent_total = models.PositiveIntegerField("意图评测数", default=0)
    tool_selection_correct = models.PositiveIntegerField("工具选择正确数", default=0)
    tool_selection_total = models.PositiveIntegerField("工具选择评测数", default=0)
    parameter_correct = models.PositiveIntegerField("参数正确数", default=0)
    parameter_total = models.PositiveIntegerField("参数评测数", default=0)
    unauthorized_blocked = models.PositiveIntegerField("越权拦截数", default=0)
    unauthorized_total = models.PositiveIntegerField("越权案例数", default=0)
    dangerous_blocked = models.PositiveIntegerField("危险操作拦截数", default=0)
    dangerous_total = models.PositiveIntegerField("危险操作案例数", default=0)
    human_escalated = models.PositiveIntegerField("人工转接数", default=0)
    human_escalation_total = models.PositiveIntegerField("人工转接评测数", default=0)
    failure_total = models.PositiveIntegerField("运行失败数", default=0)
    average_response_ms = models.PositiveIntegerField("平均响应时间（毫秒）", default=0)
    report = models.JSONField("完整评测报告", default=dict, blank=True)
    error_message = models.CharField("错误说明", max_length=255, blank=True)

    class Meta:
        verbose_name = "Agent 评测批次"
        verbose_name_plural = "Agent 评测批次"
        ordering = ("-started_at",)
        indexes = [
            models.Index(fields=["status", "started_at"]),
            models.Index(fields=["trigger", "started_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.started_at:%Y-%m-%d %H:%M} - {self.get_status_display()}"


class AgentEvaluationCaseResult(UUIDPrimaryKeyMixin, TimeStampedMixin):
    """A durable, explainable result for one case in an evaluation batch."""

    evaluation_run = models.ForeignKey(
        AgentEvaluationRun,
        verbose_name="评测批次",
        on_delete=models.CASCADE,
        related_name="case_results",
    )
    case_id = models.CharField("案例 ID", max_length=32)
    category = models.CharField("案例类别", max_length=64)
    description = models.CharField("案例说明", max_length=255)
    message = models.TextField("测试输入")
    expected_intent = models.CharField("期望意图", max_length=64)
    actual_intent = models.CharField("实际意图", max_length=64, blank=True)
    expected_tools = models.JSONField("期望工具", default=list, blank=True)
    actual_tools = models.JSONField("实际工具", default=list, blank=True)
    expected_arguments = models.JSONField("期望参数", default=list, blank=True)
    actual_arguments = models.JSONField("实际参数", default=list, blank=True)
    passed = models.BooleanField("案例通过", default=False)
    intent_passed = models.BooleanField("意图正确", default=False)
    tool_selection_passed = models.BooleanField("工具选择正确", default=False)
    parameter_applicable = models.BooleanField("参数可评测", default=False)
    parameter_passed = models.BooleanField("参数正确", null=True, blank=True)
    authorization_passed = models.BooleanField("权限断言通过", default=False)
    unauthorized_case = models.BooleanField("越权案例", default=False)
    unauthorized_blocked = models.BooleanField("越权已拦截", default=False)
    dangerous_case = models.BooleanField("危险操作案例", default=False)
    dangerous_blocked = models.BooleanField("危险操作已拦截", default=False)
    response_compliance_passed = models.BooleanField("回复合规", default=False)
    human_escalated = models.BooleanField("已转人工", default=False)
    failed = models.BooleanField("运行失败", default=False)
    response_time_ms = models.PositiveIntegerField("响应时间（毫秒）", default=0)
    actual_error_codes = models.JSONField("实际错误代码", default=list, blank=True)
    assistant_message = models.TextField("助手回复", blank=True)
    failures = models.JSONField("失败说明", default=list, blank=True)

    class Meta:
        verbose_name = "Agent 评测案例结果"
        verbose_name_plural = "Agent 评测案例结果"
        ordering = ("case_id",)
        constraints = [
            models.UniqueConstraint(
                fields=("evaluation_run", "case_id"),
                name="after_sales_unique_eval_run_case",
            )
        ]
        indexes = [
            models.Index(fields=["evaluation_run", "passed"]),
            models.Index(fields=["category", "case_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.evaluation_run_id} - {self.case_id}"


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
    run = models.ForeignKey(
        AgentRun,
        verbose_name="Agent 运行记录",
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
