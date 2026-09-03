"""Allowlisted, audited business tools for the OpenAI after-sales Agent."""

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Mapping

from rest_framework import serializers

from apps.cart_orders.models import Order, Payment

from .knowledge import KnowledgeBaseError, search_after_sales_knowledge
from .models import AgentConversation, AgentRun, ToolExecution
from .permissions import (
    ALL_TOOL_PERMISSION_LEVELS,
    ToolPermissionLevel,
    authorize_tool,
    tool_permission_matrix,
)
from .policies import AFTER_SALES_POLICIES
from .safety import (
    inspect_tool_arguments,
    inspect_tool_name,
    security_audit_arguments,
)
from .workflow import (
    AfterSalesWorkflowError,
    create_automatic_case,
    list_recent_cases,
    prepare_confirmation,
    serialize_after_sales_case,
    serialize_confirmation,
)


class ToolError(Exception):
    """A safe, structured business error that can be returned to the model."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class StrictToolArgumentsSerializer(serializers.Serializer):
    """Reject extra arguments instead of silently accepting model hallucinations."""

    def validate(self, attrs):
        unexpected = set(self.initial_data) - set(self.fields)
        if unexpected:
            raise serializers.ValidationError(
                {"unexpected_arguments": f"不支持的参数：{', '.join(sorted(unexpected))}"}
            )
        return attrs


class EmptyArgumentsSerializer(StrictToolArgumentsSerializer):
    pass


class OrderDetailArgumentsSerializer(StrictToolArgumentsSerializer):
    order_id = serializers.UUIDField()


class PrepareConfirmationArgumentsSerializer(StrictToolArgumentsSerializer):
    order_id = serializers.UUIDField()
    policy_key = serializers.ChoiceField(choices=("refund", "return-refund", "cancel-order"))
    reason = serializers.CharField(min_length=2, max_length=500, trim_whitespace=True)


class CreateAfterSalesCaseArgumentsSerializer(StrictToolArgumentsSerializer):
    policy_key = serializers.ChoiceField(
        choices=("quality-issue", "delivery-issue", "human-service")
    )
    reason = serializers.CharField(min_length=2, max_length=500, trim_whitespace=True)
    # Strict OpenAI schemas require every property; human-service calls pass null.
    order_id = serializers.UUIDField(allow_null=True)


class KnowledgeSearchArgumentsSerializer(StrictToolArgumentsSerializer):
    question = serializers.CharField(min_length=2, max_length=500, trim_whitespace=True)


@dataclass(frozen=True)
class ToolContext:
    """The only request context available to a tool handler."""

    user: Any
    conversation: AgentConversation | None = None
    run: AgentRun | None = None
    allowed_action_kinds: frozenset[str] = field(
        default_factory=lambda: frozenset({ToolExecution.ActionKind.READ})
    )
    allowed_agent_roles: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"order_analyst", "policy_advisor", "case_tracker", "workflow_specialist"}
        )
    )
    allowed_permission_levels: frozenset[str] = field(
        default_factory=lambda: ALL_TOOL_PERMISSION_LEVELS
    )


ToolHandler = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    parameters: dict[str, Any]
    arguments_serializer: type[serializers.Serializer]
    action_kind: str
    agent_role: str
    permission_level: str
    handler: ToolHandler

    def to_openai_definition(self) -> dict[str, Any]:
        """Return a Responses API Function Calling tool definition."""

        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": True,
        }


NO_ARGUMENTS_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}

ORDER_DETAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "order_id": {
            "type": "string",
            "format": "uuid",
            "description": "需要查询的订单 UUID。",
        }
    },
    "required": ["order_id"],
    "additionalProperties": False,
}

PREPARE_CONFIRMATION_SCHEMA = {
    "type": "object",
    "properties": {
        "order_id": {
            "type": "string",
            "format": "uuid",
            "description": "已核验、且属于当前用户的订单 UUID。",
        },
        "policy_key": {
            "type": "string",
            "enum": ["refund", "return-refund", "cancel-order"],
            "description": "要申请的售后类型。",
        },
        "reason": {
            "type": "string",
            "minLength": 2,
            "maxLength": 500,
            "description": "用户确认过的售后原因。",
        },
    },
    "required": ["order_id", "policy_key", "reason"],
    "additionalProperties": False,
}

CREATE_CASE_SCHEMA = {
    "type": "object",
    "properties": {
        "policy_key": {
            "type": "string",
            "enum": ["quality-issue", "delivery-issue", "human-service"],
            "description": "可直接创建受控工单的售后类型。",
        },
        "reason": {
            "type": "string",
            "minLength": 2,
            "maxLength": 500,
            "description": "用户描述的问题或诉求。",
        },
        "order_id": {
            "type": ["string", "null"],
            "format": "uuid",
            "description": "质量或物流问题必须提供订单 UUID；人工服务必须传 null。",
        },
    },
    "required": ["policy_key", "reason", "order_id"],
    "additionalProperties": False,
}

KNOWLEDGE_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "minLength": 2,
            "maxLength": 500,
            "description": "需要查询的售后知识问题，不应包含订单号、手机号等个人信息。",
        }
    },
    "required": ["question"],
    "additionalProperties": False,
}


def _serialize_order(order: Order) -> dict[str, Any]:
    try:
        payment_status = order.payment.status
    except Payment.DoesNotExist:
        payment_status = "NOT_STARTED"

    return {
        "id": str(order.id),
        "status": order.status,
        "payment_status": payment_status,
        "total_amount": str(order.total_amount),
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
            }
            for item in order.items.all()
        ],
    }


def _list_my_orders(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    orders = (
        Order.objects.filter(user=context.user)
        .select_related("payment")
        .prefetch_related("items")
        .order_by("-created_at")[:10]
    )
    return {"orders": [_serialize_order(order) for order in orders]}


def _get_my_order_detail(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        order = (
            Order.objects.filter(user=context.user)
            .select_related("payment")
            .prefetch_related("items")
            .get(id=arguments["order_id"])
        )
    except Order.DoesNotExist as exc:
        raise ToolError("ORDER_NOT_FOUND", "未找到该用户的订单。") from exc
    return {"order": _serialize_order(order)}


def _list_after_sales_policies(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "policies": [
            {
                **policy,
                "eligible_order_statuses": list(policy["eligible_order_statuses"]),
            }
            for policy in AFTER_SALES_POLICIES
        ]
    }


def _require_conversation(context: ToolContext) -> AgentConversation:
    if context.conversation is None:
        raise ToolError("CONVERSATION_REQUIRED", "该售后操作必须在已创建的会话中发起。")
    return context.conversation


def _prepare_after_sales_confirmation(
    context: ToolContext, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create a short-lived customer confirmation, never execute the action itself."""

    try:
        confirmation, reused = prepare_confirmation(
            user=context.user,
            conversation=_require_conversation(context),
            order_id=arguments["order_id"],
            policy_key=arguments["policy_key"],
            reason=arguments["reason"],
        )
    except AfterSalesWorkflowError as exc:
        raise ToolError(exc.code, exc.message) from exc
    return {
        "confirmation": serialize_confirmation(confirmation),
        "reused": reused,
        "message": "已生成待用户确认的售后申请，尚未执行取消订单或提交退款工单。",
    }


def _create_after_sales_case(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Create only a permitted, non-financial support ticket."""

    try:
        after_sales_case, reused = create_automatic_case(
            user=context.user,
            conversation=_require_conversation(context),
            policy_key=arguments["policy_key"],
            reason=arguments["reason"],
            order_id=arguments.get("order_id"),
        )
    except AfterSalesWorkflowError as exc:
        raise ToolError(exc.code, exc.message) from exc
    return {
        "after_sales_case": serialize_after_sales_case(after_sales_case),
        "reused": reused,
        "message": "售后工单已创建，等待人工处理。",
    }


def _list_my_after_sales_cases(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"cases": [serialize_after_sales_case(item) for item in list_recent_cases(user=context.user)]}


def _search_after_sales_knowledge(
    context: ToolContext, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Retrieve only trusted, static support knowledge; it never reads customer data."""

    try:
        result = search_after_sales_knowledge(arguments["question"])
    except KnowledgeBaseError as exc:
        raise ToolError("KNOWLEDGE_BASE_UNAVAILABLE", "售后知识库暂时不可用，请转人工处理。") from exc
    return {
        "matches": result.matches,
        "requires_human_escalation": result.requires_human_escalation,
        "message": result.message,
    }


REGISTERED_TOOLS = (
    RegisteredTool(
        name="list_my_orders",
        description="查询当前登录用户最近 10 笔订单及支付、物流状态。不得用于查询其他用户订单。",
        parameters=NO_ARGUMENTS_SCHEMA,
        arguments_serializer=EmptyArgumentsSerializer,
        action_kind=ToolExecution.ActionKind.READ,
        agent_role="order_analyst",
        permission_level=ToolPermissionLevel.READ_ONLY,
        handler=_list_my_orders,
    ),
    RegisteredTool(
        name="get_my_order_detail",
        description="按订单 ID 查询当前登录用户的订单明细、商品、支付和物流状态。",
        parameters=ORDER_DETAIL_SCHEMA,
        arguments_serializer=OrderDetailArgumentsSerializer,
        action_kind=ToolExecution.ActionKind.READ,
        agent_role="order_analyst",
        permission_level=ToolPermissionLevel.READ_ONLY,
        handler=_get_my_order_detail,
    ),
    RegisteredTool(
        name="list_after_sales_policies",
        description="查询退款、退货退款、取消订单、物流异常等售后规则。",
        parameters=NO_ARGUMENTS_SCHEMA,
        arguments_serializer=EmptyArgumentsSerializer,
        action_kind=ToolExecution.ActionKind.READ,
        agent_role="policy_advisor",
        permission_level=ToolPermissionLevel.READ_ONLY,
        handler=_list_after_sales_policies,
    ),
    RegisteredTool(
        name="search_after_sales_knowledge",
        description=(
            "检索经审核的售后知识库，用于尺码、面料、洗护、物流说明和非实时规则问答。"
            "绝不能用于查询订单、支付、退款、发货或其他用户信息。若返回 requires_human_escalation=true，"
            "不得猜测规则，必须转人工。"
        ),
        parameters=KNOWLEDGE_SEARCH_SCHEMA,
        arguments_serializer=KnowledgeSearchArgumentsSerializer,
        action_kind=ToolExecution.ActionKind.READ,
        agent_role="policy_advisor",
        permission_level=ToolPermissionLevel.READ_ONLY,
        handler=_search_after_sales_knowledge,
    ),
    RegisteredTool(
        name="list_my_after_sales_cases",
        description="查询当前登录用户最近 5 条售后工单及处理状态。不得查询其他用户工单。",
        parameters=NO_ARGUMENTS_SCHEMA,
        arguments_serializer=EmptyArgumentsSerializer,
        action_kind=ToolExecution.ActionKind.READ,
        agent_role="case_tracker",
        permission_level=ToolPermissionLevel.READ_ONLY,
        handler=_list_my_after_sales_cases,
    ),
    RegisteredTool(
        name="prepare_after_sales_confirmation",
        description=(
            "为退款、退货退款或待支付取消订单生成待用户确认的申请卡。"
            "它绝不会执行订单取消、退款或支付操作；调用前必须已核验订单状态和用户原因。"
        ),
        parameters=PREPARE_CONFIRMATION_SCHEMA,
        arguments_serializer=PrepareConfirmationArgumentsSerializer,
        action_kind=ToolExecution.ActionKind.WRITE,
        agent_role="workflow_specialist",
        permission_level=ToolPermissionLevel.CONFIRMATION_REQUIRED,
        handler=_prepare_after_sales_confirmation,
    ),
    RegisteredTool(
        name="create_after_sales_case",
        description=(
            "仅创建质量问题、物流异常或人工服务的受控售后工单。"
            "质量和物流问题必须提供订单 UUID；人工服务必须将 order_id 传为 null。"
            "不得用于退款、退货退款、取消订单或任何资金和订单状态变更。"
        ),
        parameters=CREATE_CASE_SCHEMA,
        arguments_serializer=CreateAfterSalesCaseArgumentsSerializer,
        action_kind=ToolExecution.ActionKind.WRITE,
        agent_role="workflow_specialist",
        permission_level=ToolPermissionLevel.GUARDED_CASE,
        handler=_create_after_sales_case,
    ),
)

TOOLS_BY_NAME = {tool.name: tool for tool in REGISTERED_TOOLS}


def get_openai_tool_definitions(
    *,
    allowed_tool_names: frozenset[str] | None = None,
    allowed_permission_levels: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Expose only allowlisted tools assigned to the active specialist team."""

    return [
        tool.to_openai_definition()
        for tool in REGISTERED_TOOLS
        if allowed_tool_names is None or tool.name in allowed_tool_names
        if allowed_permission_levels is None or tool.permission_level in allowed_permission_levels
    ]


def get_tool_permission_matrix() -> list[dict[str, str]]:
    """Expose the registered tool permission configuration to internal callers."""

    return tool_permission_matrix(REGISTERED_TOOLS)


def sanitize_tool_arguments(arguments: Any) -> dict[str, Any]:
    """Return a log-safe representation of model-supplied tool arguments."""

    if not isinstance(arguments, Mapping):
        return {"raw_arguments": "<invalid non-object arguments>"}

    safety = inspect_tool_arguments(arguments)
    if safety.blocked:
        return security_audit_arguments(arguments, safety)

    sensitive_fragments = ("password", "token", "api_key", "authorization", "secret")

    def sanitize_value(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): "***"
                if any(fragment in str(key).lower() for fragment in sensitive_fragments)
                else sanitize_value(nested_value)
                for key, nested_value in value.items()
            }
        if isinstance(value, list):
            return [sanitize_value(item) for item in value]
        return value

    return sanitize_value(arguments)


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _update_execution(
    execution: ToolExecution,
    *,
    status: str,
    result: dict[str, Any],
    error_code: str = "",
    started_at: float,
) -> None:
    execution.status = status
    execution.result = result
    execution.error_code = error_code
    execution.duration_ms = int((perf_counter() - started_at) * 1000)
    execution.save(update_fields=["status", "result", "error_code", "duration_ms"])


def execute_tool(
    context: ToolContext,
    tool_name: str,
    arguments: Any,
) -> dict[str, Any]:
    """Validate, authorize, audit, and run one allowlisted Agent tool."""

    started_at = perf_counter()
    tool_name_safety = inspect_tool_name(tool_name)
    if tool_name_safety.blocked:
        result = _error(tool_name_safety.code, tool_name_safety.message)
        ToolExecution.objects.create(
            conversation=context.conversation,
            run=context.run,
            user=context.user,
            agent_role="coordinator",
            tool_name=tool_name[:100] or "unknown",
            action_kind=ToolExecution.ActionKind.READ,
            status=ToolExecution.Status.DENIED,
            initiated_by=ToolExecution.Initiator.AGENT,
            sanitized_arguments=security_audit_arguments(arguments, tool_name_safety),
            result=result,
            error_code=tool_name_safety.code,
            duration_ms=int((perf_counter() - started_at) * 1000),
        )
        return result

    tool = TOOLS_BY_NAME.get(tool_name)
    if tool is None:
        result = _error(
            "TOOL_NOT_ALLOWED",
            "该工具不在售后 Agent 的允许列表中，不能访问数据库、命令行、文件或任意外部服务。",
        )
        ToolExecution.objects.create(
            conversation=context.conversation,
            run=context.run,
            user=context.user,
            agent_role="coordinator",
            tool_name=tool_name[:100] or "unknown",
            action_kind=ToolExecution.ActionKind.READ,
            status=ToolExecution.Status.DENIED,
            initiated_by=ToolExecution.Initiator.AGENT,
            sanitized_arguments=sanitize_tool_arguments(arguments),
            result=result,
            error_code="TOOL_NOT_ALLOWED",
            duration_ms=int((perf_counter() - started_at) * 1000),
        )
        return result

    execution = ToolExecution.objects.create(
        conversation=context.conversation,
        run=context.run,
        user=context.user,
        agent_role=tool.agent_role,
        tool_name=tool.name,
        action_kind=tool.action_kind,
        status=ToolExecution.Status.PENDING,
        initiated_by=ToolExecution.Initiator.AGENT,
        sanitized_arguments=sanitize_tool_arguments(arguments),
    )

    argument_safety = inspect_tool_arguments(arguments)
    if argument_safety.blocked:
        result = _error(argument_safety.code, argument_safety.message)
        _update_execution(
            execution,
            status=ToolExecution.Status.DENIED,
            result=result,
            error_code=argument_safety.code,
            started_at=started_at,
        )
        return result

    permission = authorize_tool(
        conversation=context.conversation,
        tool=tool,
        allowed_action_kinds=context.allowed_action_kinds,
        allowed_agent_roles=context.allowed_agent_roles,
        allowed_permission_levels=context.allowed_permission_levels,
    )
    if not permission.allowed:
        result = _error(permission.code, permission.message)
        _update_execution(
            execution,
            status=ToolExecution.Status.DENIED,
            result=result,
            error_code=permission.code,
            started_at=started_at,
        )
        return result

    if not isinstance(arguments, Mapping):
        result = _error("INVALID_ARGUMENTS", "工具参数必须是 JSON 对象。")
        _update_execution(
            execution,
            status=ToolExecution.Status.FAILED,
            result=result,
            error_code="INVALID_ARGUMENTS",
            started_at=started_at,
        )
        return result

    serializer = tool.arguments_serializer(data=dict(arguments))
    if not serializer.is_valid():
        result = _error("INVALID_ARGUMENTS", "工具参数不符合 schema。")
        result["error"]["fields"] = serializer.errors
        _update_execution(
            execution,
            status=ToolExecution.Status.FAILED,
            result=result,
            error_code="INVALID_ARGUMENTS",
            started_at=started_at,
        )
        return result

    try:
        data = tool.handler(context, serializer.validated_data)
    except ToolError as exc:
        result = _error(exc.code, exc.message)
        _update_execution(
            execution,
            status=ToolExecution.Status.FAILED,
            result=result,
            error_code=exc.code,
            started_at=started_at,
        )
        return result
    except Exception:
        result = _error("TOOL_EXECUTION_FAILED", "工具执行失败，已记录审计信息。")
        _update_execution(
            execution,
            status=ToolExecution.Status.FAILED,
            result=result,
            error_code="TOOL_EXECUTION_FAILED",
            started_at=started_at,
        )
        return result

    result = {"ok": True, "data": data}
    _update_execution(
        execution,
        status=ToolExecution.Status.SUCCEEDED,
        result=result,
        started_at=started_at,
    )
    return result
