"""Transactional confirmation and case workflows for the after-sales Agent."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from time import perf_counter
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.cart_orders.models import Order
from apps.cart_orders.services import OrderTransitionError, cancel_pending_order

from .models import AfterSalesCase, AgentConversation, AgentMessage, ConfirmationRequest, ToolExecution
from .policies import get_policy

logger = logging.getLogger(__name__)

CONFIRMATION_TTL = timedelta(minutes=10)
OPEN_CASE_STATUSES = (
    AfterSalesCase.Status.PENDING_REVIEW,
    AfterSalesCase.Status.IN_REVIEW,
    AfterSalesCase.Status.NEED_CUSTOMER_INFO,
)
CASE_PRIORITY_BY_POLICY = {
    "quality-issue": AfterSalesCase.Priority.HIGH,
    "delivery-issue": AfterSalesCase.Priority.NORMAL,
    "human-service": AfterSalesCase.Priority.NORMAL,
}
STAFF_CASE_STATUS_TRANSITIONS = {
    AfterSalesCase.Status.PENDING_REVIEW: frozenset(
        {
            AfterSalesCase.Status.IN_REVIEW,
            AfterSalesCase.Status.NEED_CUSTOMER_INFO,
            AfterSalesCase.Status.APPROVED,
            AfterSalesCase.Status.REJECTED,
            AfterSalesCase.Status.CLOSED,
        }
    ),
    AfterSalesCase.Status.IN_REVIEW: frozenset(
        {
            AfterSalesCase.Status.NEED_CUSTOMER_INFO,
            AfterSalesCase.Status.APPROVED,
            AfterSalesCase.Status.REJECTED,
            AfterSalesCase.Status.CLOSED,
        }
    ),
    AfterSalesCase.Status.NEED_CUSTOMER_INFO: frozenset(
        {
            AfterSalesCase.Status.IN_REVIEW,
            AfterSalesCase.Status.APPROVED,
            AfterSalesCase.Status.REJECTED,
            AfterSalesCase.Status.CLOSED,
        }
    ),
    AfterSalesCase.Status.APPROVED: frozenset({AfterSalesCase.Status.CLOSED}),
    AfterSalesCase.Status.REJECTED: frozenset({AfterSalesCase.Status.CLOSED}),
    AfterSalesCase.Status.CLOSED: frozenset(),
    AfterSalesCase.Status.CANCELLED: frozenset(),
}


class AfterSalesWorkflowError(Exception):
    """A safe business error for APIs and Agent tools."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ConfirmationExecutionResult:
    confirmation: ConfirmationRequest
    after_sales_case: AfterSalesCase | None
    order: Order | None
    already_executed: bool = False


def _order_summary(order: Order | None) -> dict[str, Any] | None:
    if order is None:
        return None
    return {
        "id": str(order.id),
        "status": order.status,
        "total_amount": str(order.total_amount),
        "items": [
            {"product_name": item.product_name, "quantity": item.quantity}
            for item in order.items.all()
        ],
    }


def serialize_confirmation(confirmation: ConfirmationRequest) -> dict[str, Any]:
    """Expose only the customer-facing, owner-scoped confirmation fields."""

    policy = get_policy(confirmation.payload.get("policy_key", ""))
    return {
        "id": str(confirmation.id),
        "status": confirmation.status,
        "action_type": confirmation.action_type,
        "action_label": confirmation.get_action_type_display(),
        "policy_key": confirmation.payload.get("policy_key", ""),
        "policy_name": policy["name"] if policy else confirmation.get_action_type_display(),
        "reason": confirmation.payload.get("reason", ""),
        "order": _order_summary(confirmation.order),
        "expires_at": confirmation.expires_at.isoformat(),
        "created_at": confirmation.created_at.isoformat(),
    }


def serialize_after_sales_case(after_sales_case: AfterSalesCase) -> dict[str, Any]:
    return {
        "id": str(after_sales_case.id),
        "case_number": after_sales_case.case_number,
        "case_type": after_sales_case.case_type,
        "case_type_label": after_sales_case.get_case_type_display(),
        "status": after_sales_case.status,
        "status_label": after_sales_case.get_status_display(),
        "priority": after_sales_case.priority,
        "reason": after_sales_case.reason,
        "order": _order_summary(after_sales_case.order),
        "created_at": after_sales_case.created_at.isoformat(),
    }


def _get_owned_order(*, user: Any, order_id: Any) -> Order:
    try:
        return Order.objects.prefetch_related("items").get(id=order_id, user=user)
    except Order.DoesNotExist as exc:
        raise AfterSalesWorkflowError("ORDER_NOT_FOUND", "未找到该用户的订单。") from exc


def _validate_reason(reason: str) -> str:
    normalized = reason.strip()
    if len(normalized) < 2:
        raise AfterSalesWorkflowError("REASON_REQUIRED", "请补充至少两个字的售后原因。")
    if len(normalized) > 500:
        raise AfterSalesWorkflowError("REASON_TOO_LONG", "售后原因不能超过 500 个字符。")
    return normalized


def _validate_policy(policy_key: str, *, requires_confirmation: bool) -> dict[str, Any]:
    policy = get_policy(policy_key)
    if policy is None:
        raise AfterSalesWorkflowError("POLICY_NOT_FOUND", "未找到对应的售后处理规则。")
    if policy["requires_confirmation"] is not requires_confirmation:
        raise AfterSalesWorkflowError("POLICY_ACTION_NOT_ALLOWED", "该规则不能通过当前操作处理。")
    return policy


def _validate_order_status(order: Order, policy: dict[str, Any]) -> None:
    if order.status not in policy["eligible_order_statuses"]:
        raise AfterSalesWorkflowError(
            "ORDER_STATUS_NOT_ELIGIBLE",
            f"当前订单状态不符合“{policy['name']}”的申请条件。",
        )


def get_pending_confirmation(conversation: AgentConversation) -> ConfirmationRequest | None:
    """Return one live pending confirmation, expiring stale cards as part of the read."""

    now = timezone.now()
    expired_count = ConfirmationRequest.objects.filter(
        conversation=conversation,
        status=ConfirmationRequest.Status.PENDING,
        expires_at__lte=now,
    ).update(status=ConfirmationRequest.Status.EXPIRED, result={"message": "确认申请已过期。"})
    if expired_count and conversation.state == AgentConversation.State.AWAITING_CONFIRMATION:
        conversation.state = AgentConversation.State.ACTIVE
        conversation.save(update_fields=["state", "updated_at"])
    return (
        ConfirmationRequest.objects.filter(
            conversation=conversation,
            status=ConfirmationRequest.Status.PENDING,
            expires_at__gt=now,
        )
        .select_related("order")
        .prefetch_related("order__items")
        .order_by("-created_at")
        .first()
    )


def list_recent_cases(*, user: Any, limit: int = 5) -> list[AfterSalesCase]:
    return list(
        AfterSalesCase.objects.filter(user=user)
        .select_related("order")
        .prefetch_related("order__items")
        .order_by("-created_at")[:limit]
    )


def list_staff_cases(
    *,
    status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[AfterSalesCase]:
    """Return a bounded, searchable work queue for authenticated staff."""

    cases = (
        AfterSalesCase.objects.select_related("user", "order", "assigned_to", "conversation")
        .prefetch_related("order__items")
        .order_by("-updated_at")
    )
    if status:
        cases = cases.filter(status=status)
    if priority:
        cases = cases.filter(priority=priority)
    if search:
        cases = cases.filter(
            Q(case_number__icontains=search)
            | Q(user__username__icontains=search)
            | Q(reason__icontains=search)
        )
    return list(cases[:limit])


def list_staff_orders(
    *,
    status: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[Order]:
    """Return a bounded fulfillment queue, independent of after-sales tickets."""

    orders = Order.objects.select_related("user").prefetch_related("items").order_by("-created_at")
    if status:
        orders = orders.filter(status=status)
    if search:
        orders = orders.filter(
            Q(user__username__icontains=search) | Q(items__product_name__icontains=search)
        ).distinct()
    return list(orders[:limit])


def serialize_staff_order(order: Order) -> dict[str, Any]:
    """Return the operational fields staff need to fulfill one order."""

    return {
        "id": str(order.id),
        "status": order.status,
        "status_label": order.get_status_display(),
        "total_amount": str(order.total_amount),
        "shipping_address": order.shipping_address,
        "user": {
            "id": order.user_id,
            "username": order.user.username,
            "phone_number": str(order.user.phone_number),
        },
        "items": [
            {
                "product_name": item.product_name,
                "unit_price": str(item.unit_price),
                "quantity": item.quantity,
                "line_total": str(item.line_total),
            }
            for item in order.items.all()
        ],
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }


def serialize_staff_case(
    after_sales_case: AfterSalesCase,
    *,
    include_conversation: bool = False,
) -> dict[str, Any]:
    """Return staff-visible case data without exposing raw model tool activity."""

    payload = {
        **serialize_after_sales_case(after_sales_case),
        "updated_at": after_sales_case.updated_at.isoformat(),
        "resolved_at": (
            after_sales_case.resolved_at.isoformat() if after_sales_case.resolved_at else None
        ),
        "agent_summary": after_sales_case.agent_summary,
        "staff_note": after_sales_case.staff_note,
        "user": {
            "id": after_sales_case.user_id,
            "username": after_sales_case.user.username,
            "phone_number": str(after_sales_case.user.phone_number),
        },
        "assigned_to": (
            {"id": after_sales_case.assigned_to_id, "username": after_sales_case.assigned_to.username}
            if after_sales_case.assigned_to_id
            else None
        ),
    }
    if include_conversation:
        conversation = after_sales_case.conversation
        payload["conversation"] = (
            {
                "id": str(conversation.id),
                "state": conversation.state,
                "summary": conversation.summary,
                "messages": [
                    {
                        "id": message.id,
                        "role": message.role,
                        "content": message.content,
                        "created_at": message.created_at.isoformat(),
                    }
                    for message in conversation.messages.filter(
                        role__in=(AgentMessage.Role.USER, AgentMessage.Role.ASSISTANT)
                    ).order_by("created_at")
                ],
            }
            if conversation
            else None
        )
    return payload


def update_staff_case(
    *,
    staff_user: Any,
    case_id: Any,
    status: str | None = None,
    staff_note: str | None = None,
) -> AfterSalesCase:
    """Perform one validated staff resolution action and write a human audit record."""

    with transaction.atomic():
        try:
            after_sales_case = (
                AfterSalesCase.objects.select_for_update(of=("self",))
                .select_related("user", "order", "assigned_to", "conversation")
                .prefetch_related("order__items")
                .get(id=case_id)
            )
        except AfterSalesCase.DoesNotExist as exc:
            raise AfterSalesWorkflowError("CASE_NOT_FOUND", "未找到该售后工单。") from exc

        changed_fields = ["updated_at"]
        previous_status = after_sales_case.status
        if status and status != previous_status:
            allowed_statuses = STAFF_CASE_STATUS_TRANSITIONS.get(previous_status, frozenset())
            if status not in allowed_statuses:
                raise AfterSalesWorkflowError(
                    "INVALID_CASE_TRANSITION",
                    "当前工单状态不能流转到所选状态。",
                )
            after_sales_case.status = status
            changed_fields.append("status")
            if status in {
                AfterSalesCase.Status.APPROVED,
                AfterSalesCase.Status.REJECTED,
                AfterSalesCase.Status.CLOSED,
            }:
                after_sales_case.resolved_at = timezone.now()
                changed_fields.append("resolved_at")

        if staff_note is not None and staff_note != after_sales_case.staff_note:
            after_sales_case.staff_note = staff_note
            changed_fields.append("staff_note")

        if len(changed_fields) == 1:
            raise AfterSalesWorkflowError("NO_CASE_CHANGES", "请修改处理状态或客服备注后再保存。")

        after_sales_case.assigned_to = staff_user
        changed_fields.append("assigned_to")
        after_sales_case.save(update_fields=changed_fields)
        ToolExecution.objects.create(
            conversation=after_sales_case.conversation,
            user=after_sales_case.user,
            after_sales_case=after_sales_case,
            tool_name="staff_update_after_sales_case",
            action_kind=ToolExecution.ActionKind.WRITE,
            status=ToolExecution.Status.SUCCEEDED,
            initiated_by=ToolExecution.Initiator.HUMAN,
            agent_role="staff_workbench",
            sanitized_arguments={
                "case_number": after_sales_case.case_number,
                "previous_status": previous_status,
                "status": after_sales_case.status,
                "note_updated": staff_note is not None,
            },
            result={"assigned_to": staff_user.username},
            duration_ms=0,
        )
        return after_sales_case


def ship_staff_case_order(*, staff_user: Any, case_id: Any) -> AfterSalesCase:
    """Mark the paid order attached to a case as shipped and audit the human action."""

    with transaction.atomic():
        try:
            after_sales_case = AfterSalesCase.objects.select_for_update().get(id=case_id)
        except AfterSalesCase.DoesNotExist as exc:
            raise AfterSalesWorkflowError("CASE_NOT_FOUND", "未找到该售后工单。") from exc

        if not after_sales_case.order_id:
            raise AfterSalesWorkflowError("CASE_ORDER_NOT_FOUND", "该工单没有关联订单，无法发货。")

        order = Order.objects.select_for_update().get(id=after_sales_case.order_id)
        if order.status != Order.Status.PAID:
            raise AfterSalesWorkflowError("ORDER_NOT_READY_TO_SHIP", "只有已支付订单可以标记为已发货。")

        order.status = Order.Status.SHIPPED
        order.save(update_fields=["status"])
        after_sales_case.assigned_to = staff_user
        after_sales_case.save(update_fields=["assigned_to", "updated_at"])
        ToolExecution.objects.create(
            conversation_id=after_sales_case.conversation_id,
            user_id=after_sales_case.user_id,
            after_sales_case=after_sales_case,
            tool_name="staff_ship_order",
            action_kind=ToolExecution.ActionKind.WRITE,
            status=ToolExecution.Status.SUCCEEDED,
            initiated_by=ToolExecution.Initiator.HUMAN,
            agent_role="staff_workbench",
            sanitized_arguments={
                "case_number": after_sales_case.case_number,
                "order_id": str(order.id),
                "previous_status": Order.Status.PAID,
                "status": Order.Status.SHIPPED,
            },
            result={"assigned_to": staff_user.username},
            duration_ms=0,
        )
        return AfterSalesCase.objects.select_related("user", "order", "assigned_to", "conversation").prefetch_related(
            "order__items"
        ).get(id=after_sales_case.id)


def refund_staff_case_order(*, staff_user: Any, case_id: Any) -> AfterSalesCase:
    """Finish an approved refund case by marking its linked order as refunded."""

    with transaction.atomic():
        try:
            after_sales_case = AfterSalesCase.objects.select_for_update().get(id=case_id)
        except AfterSalesCase.DoesNotExist as exc:
            raise AfterSalesWorkflowError("CASE_NOT_FOUND", "未找到该售后工单。") from exc

        if after_sales_case.case_type not in {
            AfterSalesCase.CaseType.REFUND,
            AfterSalesCase.CaseType.RETURN_REFUND,
        }:
            raise AfterSalesWorkflowError("CASE_NOT_REFUNDABLE", "只有退款或退货退款工单可以标记已退款。")
        if after_sales_case.status != AfterSalesCase.Status.APPROVED:
            raise AfterSalesWorkflowError("CASE_NOT_APPROVED_FOR_REFUND", "请先通过该退款工单，再标记已退款。")
        if not after_sales_case.order_id:
            raise AfterSalesWorkflowError("CASE_ORDER_NOT_FOUND", "该工单没有关联订单，无法标记退款。")

        order = Order.objects.select_for_update().get(id=after_sales_case.order_id)
        if order.status not in {Order.Status.PAID, Order.Status.SHIPPED}:
            raise AfterSalesWorkflowError("ORDER_NOT_REFUNDABLE", "当前订单状态不能标记为已退款。")

        previous_status = order.status
        order.status = Order.Status.REFUNDED
        order.save(update_fields=["status", "updated_at"])
        after_sales_case.status = AfterSalesCase.Status.CLOSED
        after_sales_case.assigned_to = staff_user
        after_sales_case.resolved_at = timezone.now()
        after_sales_case.save(update_fields=["status", "assigned_to", "resolved_at", "updated_at"])
        ToolExecution.objects.create(
            conversation_id=after_sales_case.conversation_id,
            user_id=after_sales_case.user_id,
            after_sales_case=after_sales_case,
            tool_name="staff_refund_order",
            action_kind=ToolExecution.ActionKind.WRITE,
            status=ToolExecution.Status.SUCCEEDED,
            initiated_by=ToolExecution.Initiator.HUMAN,
            agent_role="staff_workbench",
            sanitized_arguments={
                "case_number": after_sales_case.case_number,
                "case_type": after_sales_case.case_type,
                "order_id": str(order.id),
                "previous_status": previous_status,
                "status": Order.Status.REFUNDED,
            },
            result={"assigned_to": staff_user.username},
            duration_ms=0,
        )
        return AfterSalesCase.objects.select_related("user", "order", "assigned_to", "conversation").prefetch_related(
            "order__items"
        ).get(id=after_sales_case.id)


def ship_staff_order(*, staff_user: Any, order_id: Any) -> Order:
    """Mark any paid order as shipped from the staff fulfillment queue."""

    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(id=order_id)
        except Order.DoesNotExist as exc:
            raise AfterSalesWorkflowError("ORDER_NOT_FOUND", "未找到该订单。") from exc

        if order.status != Order.Status.PAID:
            raise AfterSalesWorkflowError("ORDER_NOT_READY_TO_SHIP", "只有已支付订单可以标记为已发货。")

        order.status = Order.Status.SHIPPED
        order.save(update_fields=["status", "updated_at"])
        ToolExecution.objects.create(
            user_id=order.user_id,
            tool_name="staff_ship_order",
            action_kind=ToolExecution.ActionKind.WRITE,
            status=ToolExecution.Status.SUCCEEDED,
            initiated_by=ToolExecution.Initiator.HUMAN,
            agent_role="staff_workbench",
            sanitized_arguments={
                "order_id": str(order.id),
                "previous_status": Order.Status.PAID,
                "status": Order.Status.SHIPPED,
            },
            result={"assigned_to": staff_user.username},
            duration_ms=0,
        )
        return Order.objects.select_related("user").prefetch_related("items").get(id=order.id)


def prepare_confirmation(
    *,
    user: Any,
    conversation: AgentConversation,
    order_id: Any,
    policy_key: str,
    reason: str,
) -> tuple[ConfirmationRequest, bool]:
    """Create or reuse a short-lived confirmation without performing the action."""

    policy = _validate_policy(policy_key, requires_confirmation=True)
    order = _get_owned_order(user=user, order_id=order_id)
    _validate_order_status(order, policy)
    reason = _validate_reason(reason)
    now = timezone.now()

    with transaction.atomic():
        existing = (
            ConfirmationRequest.objects.select_for_update()
            .filter(
                conversation=conversation,
                user=user,
                order=order,
                action_type=policy["confirmation_action"],
                status=ConfirmationRequest.Status.PENDING,
            )
            .order_by("-created_at")
            .first()
        )
        if existing and existing.expires_at > now:
            return existing, True
        if existing:
            existing.status = ConfirmationRequest.Status.EXPIRED
            existing.result = {"message": "确认申请已过期。"}
            existing.save(update_fields=["status", "result", "updated_at"])

        confirmation = ConfirmationRequest.objects.create(
            conversation=conversation,
            user=user,
            order=order,
            action_type=policy["confirmation_action"],
            payload={"policy_key": policy_key, "reason": reason},
            expires_at=now + CONFIRMATION_TTL,
        )
        conversation.state = AgentConversation.State.AWAITING_CONFIRMATION
        conversation.save(update_fields=["state", "updated_at"])
        return confirmation, False


def create_automatic_case(
    *,
    user: Any,
    conversation: AgentConversation,
    policy_key: str,
    reason: str,
    order_id: Any = None,
) -> tuple[AfterSalesCase, bool]:
    """Create a low-risk support ticket only for policies that allow it directly."""

    policy = _validate_policy(policy_key, requires_confirmation=False)
    reason = _validate_reason(reason)
    order = None
    if order_id is not None:
        order = _get_owned_order(user=user, order_id=order_id)
        _validate_order_status(order, policy)
    elif policy_key != "human-service":
        raise AfterSalesWorkflowError("ORDER_REQUIRED", "该售后问题需要先指定对应订单。")

    with transaction.atomic():
        existing_cases = AfterSalesCase.objects.select_for_update().filter(
            user=user,
            conversation=conversation,
            case_type=policy["case_type"],
            status__in=OPEN_CASE_STATUSES,
        )
        if order is None:
            existing = existing_cases.filter(order__isnull=True).first()
        else:
            existing = existing_cases.filter(order=order).first()
        if existing:
            return existing, True

        after_sales_case = AfterSalesCase.objects.create(
            user=user,
            order=order,
            conversation=conversation,
            case_type=policy["case_type"],
            priority=CASE_PRIORITY_BY_POLICY[policy_key],
            reason=reason,
            agent_summary=f"Agent 根据“{policy['name']}”规则创建的售后工单。",
        )
        if policy_key == "human-service":
            conversation.state = AgentConversation.State.ESCALATED
            conversation.save(update_fields=["state", "updated_at"])
        return after_sales_case, False


def create_system_exception_case(
    *,
    user: Any,
    conversation: AgentConversation,
    tool_name: str,
    error_code: str,
    failure_count: int,
) -> tuple[AfterSalesCase, bool]:
    """Escalate repeated tool failures once, without exposing internal details to customers."""

    safe_tool_name = tool_name[:100] or "unknown"
    safe_error_code = error_code[:100] or "TOOL_EXECUTION_FAILED"
    with transaction.atomic():
        existing = (
            AfterSalesCase.objects.select_for_update()
            .filter(
                user=user,
                conversation=conversation,
                case_type=AfterSalesCase.CaseType.SYSTEM_EXCEPTION,
                status__in=OPEN_CASE_STATUSES,
            )
            .order_by("-created_at")
            .first()
        )
        if existing:
            after_sales_case = existing
            reused = True
        else:
            after_sales_case = AfterSalesCase.objects.create(
                user=user,
                conversation=conversation,
                case_type=AfterSalesCase.CaseType.SYSTEM_EXCEPTION,
                priority=AfterSalesCase.Priority.HIGH,
                reason="售后助手在核验过程中连续遇到异常，已自动转人工处理。",
                agent_summary=(
                    f"工具 {safe_tool_name} 连续失败 {failure_count} 次，"
                    f"最后错误代码：{safe_error_code}。"
                ),
            )
            reused = False

        conversation.state = AgentConversation.State.ESCALATED
        conversation.save(update_fields=["state", "updated_at"])
        ToolExecution.objects.create(
            conversation=conversation,
            user=user,
            after_sales_case=after_sales_case,
            tool_name="escalate_system_exception",
            action_kind=ToolExecution.ActionKind.WRITE,
            status=ToolExecution.Status.SUCCEEDED,
            initiated_by=ToolExecution.Initiator.SYSTEM,
            agent_role="coordinator",
            sanitized_arguments={
                "failed_tool": safe_tool_name,
                "failure_count": failure_count,
            },
            result={"case_number": after_sales_case.case_number, "reused": reused},
            error_code=safe_error_code,
            duration_ms=0,
        )
        return after_sales_case, reused


def _write_human_audit(
    *,
    confirmation: ConfirmationRequest,
    status: str,
    result: dict[str, Any],
    started_at: float,
    after_sales_case: AfterSalesCase | None = None,
    error_code: str = "",
) -> None:
    ToolExecution.objects.create(
        conversation=confirmation.conversation,
        user=confirmation.user,
        after_sales_case=after_sales_case,
        confirmation_request=confirmation,
        tool_name="confirm_after_sales_request",
        action_kind=ToolExecution.ActionKind.WRITE,
        status=status,
        initiated_by=ToolExecution.Initiator.HUMAN,
        sanitized_arguments={"confirmation_id": str(confirmation.id)},
        result=result,
        error_code=error_code,
        duration_ms=int((perf_counter() - started_at) * 1000),
    )


def _mark_confirmation_failed(
    *,
    confirmation: ConfirmationRequest,
    message: str,
    error_code: str,
    started_at: float,
) -> AfterSalesWorkflowError:
    """Persist a safe failure result after the inner business transaction has rolled back."""

    confirmation.status = ConfirmationRequest.Status.FAILED
    confirmation.result = {"message": message}
    confirmation.save(update_fields=["status", "result", "updated_at"])
    _write_human_audit(
        confirmation=confirmation,
        status=ToolExecution.Status.FAILED,
        result=confirmation.result,
        error_code=error_code,
        started_at=started_at,
    )
    return AfterSalesWorkflowError(error_code, message)


def execute_confirmation(*, user: Any, confirmation_id: Any) -> ConfirmationExecutionResult:
    """Execute one confirmed request exactly once, using a row lock and audit record."""

    started_at = perf_counter()
    error: AfterSalesWorkflowError | None = None
    execution_result: ConfirmationExecutionResult | None = None
    with transaction.atomic():
        try:
            confirmation = (
                ConfirmationRequest.objects.select_for_update(of=("self",))
                .select_related("conversation", "order")
                .prefetch_related("order__items")
                .get(id=confirmation_id, user=user)
            )
        except ConfirmationRequest.DoesNotExist as exc:
            raise AfterSalesWorkflowError("CONFIRMATION_NOT_FOUND", "未找到该确认申请。") from exc

        if confirmation.status == ConfirmationRequest.Status.EXECUTED:
            try:
                after_sales_case = confirmation.after_sales_case
            except AfterSalesCase.DoesNotExist:
                after_sales_case = None
            return ConfirmationExecutionResult(
                confirmation=confirmation,
                after_sales_case=after_sales_case,
                order=confirmation.order,
                already_executed=True,
            )
        if confirmation.status != ConfirmationRequest.Status.PENDING:
            raise AfterSalesWorkflowError("CONFIRMATION_NOT_PENDING", "该确认申请当前不能执行。")
        if confirmation.expires_at <= timezone.now():
            confirmation.status = ConfirmationRequest.Status.EXPIRED
            confirmation.result = {"message": "确认申请已过期，请重新发起。"}
            confirmation.save(update_fields=["status", "result", "updated_at"])
            error = AfterSalesWorkflowError("CONFIRMATION_EXPIRED", "确认申请已过期，请重新发起。")
        else:
            policy = get_policy(confirmation.payload.get("policy_key", ""))
            if policy is None:
                raise AfterSalesWorkflowError("POLICY_NOT_FOUND", "确认申请对应的规则不存在。")

            try:
                # A savepoint lets us record a failed confirmation after rolling back any partial write.
                with transaction.atomic():
                    if confirmation.action_type == ConfirmationRequest.ActionType.CANCEL_ORDER:
                        order = cancel_pending_order(confirmation.order_id, user=user)
                        after_sales_case = None
                        result = {"message": "订单已取消。", "order": _order_summary(order)}
                    else:
                        after_sales_case = AfterSalesCase.objects.create(
                            user=user,
                            order=confirmation.order,
                            conversation=confirmation.conversation,
                            confirmation_request=confirmation,
                            case_type=policy["case_type"],
                            priority=AfterSalesCase.Priority.NORMAL,
                            reason=confirmation.payload.get("reason", ""),
                            agent_summary=f"用户确认提交的“{policy['name']}”。",
                        )
                        order = confirmation.order
                        result = {
                            "message": f"售后工单 {after_sales_case.case_number} 已提交，等待人工审核。",
                            "after_sales_case": serialize_after_sales_case(after_sales_case),
                        }
            except OrderTransitionError as exc:
                error = _mark_confirmation_failed(
                    confirmation=confirmation,
                    message=str(exc),
                    error_code="ORDER_TRANSITION_FAILED",
                    started_at=started_at,
                )
            except Exception:
                logger.exception("After-sales confirmation execution failed")
                error = _mark_confirmation_failed(
                    confirmation=confirmation,
                    message="售后申请处理失败，未创建工单或修改订单，请稍后重新发起。",
                    error_code="CONFIRMATION_EXECUTION_FAILED",
                    started_at=started_at,
                )
            else:
                confirmation.status = ConfirmationRequest.Status.EXECUTED
                confirmation.confirmed_at = timezone.now()
                confirmation.executed_at = timezone.now()
                confirmation.result = result
                confirmation.save(
                    update_fields=["status", "confirmed_at", "executed_at", "result", "updated_at"]
                )
                confirmation.conversation.state = AgentConversation.State.ACTIVE
                confirmation.conversation.save(update_fields=["state", "updated_at"])
                _write_human_audit(
                    confirmation=confirmation,
                    status=ToolExecution.Status.SUCCEEDED,
                    result=result,
                    after_sales_case=after_sales_case,
                    started_at=started_at,
                )
                execution_result = ConfirmationExecutionResult(confirmation, after_sales_case, order)

    if error is not None:
        raise error
    if execution_result is None:
        raise AfterSalesWorkflowError("CONFIRMATION_EXECUTION_FAILED", "确认申请执行失败。")
    return execution_result


def reject_confirmation(*, user: Any, confirmation_id: Any) -> ConfirmationRequest:
    """Reject a pending request without changing an order or creating a ticket."""

    with transaction.atomic():
        try:
            confirmation = ConfirmationRequest.objects.select_for_update().get(
                id=confirmation_id, user=user
            )
        except ConfirmationRequest.DoesNotExist as exc:
            raise AfterSalesWorkflowError("CONFIRMATION_NOT_FOUND", "未找到该确认申请。") from exc
        if confirmation.status == ConfirmationRequest.Status.REJECTED:
            return confirmation
        if confirmation.status != ConfirmationRequest.Status.PENDING:
            raise AfterSalesWorkflowError("CONFIRMATION_NOT_PENDING", "该确认申请当前不能拒绝。")
        if confirmation.expires_at <= timezone.now():
            confirmation.status = ConfirmationRequest.Status.EXPIRED
            confirmation.result = {"message": "确认申请已过期。"}
        else:
            confirmation.status = ConfirmationRequest.Status.REJECTED
            confirmation.result = {"message": "用户已取消本次售后提交。"}
        confirmation.save(update_fields=["status", "result", "updated_at"])
        confirmation.conversation.state = AgentConversation.State.ACTIVE
        confirmation.conversation.save(update_fields=["state", "updated_at"])
        return confirmation
