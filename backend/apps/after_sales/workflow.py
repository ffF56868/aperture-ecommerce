"""Transactional confirmation and case workflows for the after-sales Agent."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from time import perf_counter
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.cart_orders.models import Order
from apps.cart_orders.services import OrderTransitionError, cancel_pending_order

from .models import AfterSalesCase, AgentConversation, ConfirmationRequest, ToolExecution
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
