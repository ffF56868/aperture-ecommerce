"""Allowlisted, audited business tools for the OpenAI after-sales Agent."""

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Mapping

from rest_framework import serializers

from apps.cart_orders.models import Order, Payment

from .models import AgentConversation, ToolExecution
from .policies import AFTER_SALES_POLICIES


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


@dataclass(frozen=True)
class ToolContext:
    """The only request context available to a tool handler."""

    user: Any
    conversation: AgentConversation | None = None
    allowed_action_kinds: frozenset[str] = field(
        default_factory=lambda: frozenset({ToolExecution.ActionKind.READ})
    )


ToolHandler = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    parameters: dict[str, Any]
    arguments_serializer: type[serializers.Serializer]
    action_kind: str
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


REGISTERED_TOOLS = (
    RegisteredTool(
        name="list_my_orders",
        description="查询当前登录用户最近 10 笔订单及支付、物流状态。不得用于查询其他用户订单。",
        parameters=NO_ARGUMENTS_SCHEMA,
        arguments_serializer=EmptyArgumentsSerializer,
        action_kind=ToolExecution.ActionKind.READ,
        handler=_list_my_orders,
    ),
    RegisteredTool(
        name="get_my_order_detail",
        description="按订单 ID 查询当前登录用户的订单明细、商品、支付和物流状态。",
        parameters=ORDER_DETAIL_SCHEMA,
        arguments_serializer=OrderDetailArgumentsSerializer,
        action_kind=ToolExecution.ActionKind.READ,
        handler=_get_my_order_detail,
    ),
    RegisteredTool(
        name="list_after_sales_policies",
        description="查询退款、退货退款、取消订单、物流异常等售后规则。",
        parameters=NO_ARGUMENTS_SCHEMA,
        arguments_serializer=EmptyArgumentsSerializer,
        action_kind=ToolExecution.ActionKind.READ,
        handler=_list_after_sales_policies,
    ),
)

TOOLS_BY_NAME = {tool.name: tool for tool in REGISTERED_TOOLS}


def get_openai_tool_definitions() -> list[dict[str, Any]]:
    """Expose only the allowlisted business tools to OpenAI."""

    return [tool.to_openai_definition() for tool in REGISTERED_TOOLS]


def sanitize_tool_arguments(arguments: Any) -> dict[str, Any]:
    """Return a log-safe representation of model-supplied tool arguments."""

    if not isinstance(arguments, Mapping):
        return {"raw_arguments": "<invalid non-object arguments>"}

    sensitive_fragments = ("password", "token", "api_key", "authorization", "secret")
    sanitized = {}
    for key, value in arguments.items():
        if any(fragment in key.lower() for fragment in sensitive_fragments):
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


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
    tool = TOOLS_BY_NAME.get(tool_name)
    if tool is None:
        result = _error(
            "TOOL_NOT_ALLOWED",
            "该工具不在售后 Agent 的允许列表中，不能访问数据库、命令行、文件或任意外部服务。",
        )
        ToolExecution.objects.create(
            conversation=context.conversation,
            user=context.user,
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
        user=context.user,
        tool_name=tool.name,
        action_kind=tool.action_kind,
        status=ToolExecution.Status.PENDING,
        initiated_by=ToolExecution.Initiator.AGENT,
        sanitized_arguments=sanitize_tool_arguments(arguments),
    )

    if tool.action_kind not in context.allowed_action_kinds:
        result = _error("TOOL_PERMISSION_DENIED", "当前会话没有执行该工具的权限。")
        _update_execution(
            execution,
            status=ToolExecution.Status.DENIED,
            result=result,
            error_code="TOOL_PERMISSION_DENIED",
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
