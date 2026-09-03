"""API endpoints for after-sales rules and the controlled Agent conversation."""

import logging

from django.db.models import Avg, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart_orders.models import Order

from .agent_service import (
    AfterSalesAgentUnavailableError,
    mark_active_agent_run_failed,
    run_agent_turn,
)
from .collaboration import get_stored_plan_payload
from .models import (
    AfterSalesCase,
    AfterSalesNotification,
    AgentConversation,
    AgentMessage,
    AgentRun,
    AgentRunEvent,
    ToolExecution,
)
from .openai_client import OpenAIConfigurationError
from .policies import AFTER_SALES_POLICIES, get_policy
from .serializers import (
    AfterSalesPolicySerializer,
    AgentConversationDetailSerializer,
    AgentConversationTurnSerializer,
    AgentMessageHistorySerializer,
    AfterSalesCaseResponseSerializer,
    AfterSalesNotificationListSerializer,
    AfterSalesNotificationReadAllSerializer,
    AfterSalesNotificationSerializer,
    StaffAfterSalesCaseSerializer,
    StaffAfterSalesCaseUpdateSerializer,
    StaffOrderSerializer,
    AgentRunDetailSerializer,
    AgentRunListResponseSerializer,
    ConfirmationExecutionSerializer,
    ConfirmationRejectionSerializer,
    ConversationMessageRequestSerializer,
)
from .workflow import (
    AfterSalesWorkflowError,
    execute_confirmation,
    get_pending_confirmation,
    list_recent_cases,
    list_staff_cases,
    list_staff_orders,
    reject_confirmation,
    serialize_after_sales_case,
    serialize_confirmation,
    serialize_staff_case,
    serialize_staff_order,
    refund_staff_case_order,
    ship_staff_case_order,
    ship_staff_order,
    update_staff_case,
)
from .notifications import (
    mark_all_notifications_read,
    mark_notification_read,
    serialize_notification,
)

logger = logging.getLogger(__name__)


def _staff_user_payload(user):
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "phone_number": str(user.phone_number),
    }


def _serialize_agent_run_list_item(run):
    return {
        "id": run.id,
        "conversation_id": run.conversation_id,
        "user": _staff_user_payload(run.user),
        "model_name": run.model_name,
        "current_intent": run.current_intent,
        "input_preview": run.input_message.replace("\n", " ")[:120],
        "status": run.status,
        "status_label": run.get_status_display(),
        "tool_rounds": run.tool_rounds,
        "tool_call_count": run.tool_call_count,
        "successful_tool_count": run.successful_tool_count,
        "failed_tool_count": run.failed_tool_count,
        "denied_tool_count": run.denied_tool_count,
        "total_tokens": run.total_tokens,
        "duration_ms": run.duration_ms,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


def _serialize_agent_run_event(event):
    return {
        "id": event.id,
        "event_type": event.event_type,
        "status": event.status,
        "sequence": event.sequence,
        "name": event.name,
        "detail": event.detail,
        "duration_ms": event.duration_ms,
        "created_at": event.created_at,
    }


def _serialize_agent_run_tool_execution(execution):
    return {
        "id": execution.id,
        "tool_name": execution.tool_name,
        "agent_role": execution.agent_role,
        "action_kind": execution.action_kind,
        "status": execution.status,
        "initiated_by": execution.initiated_by,
        "sanitized_arguments": execution.sanitized_arguments,
        "result": execution.result,
        "error_code": execution.error_code,
        "duration_ms": execution.duration_ms,
        "created_at": execution.created_at,
    }


def _serialize_agent_run_detail(run):
    return {
        **_serialize_agent_run_list_item(run),
        "input_message": run.input_message,
        "assistant_message": run.assistant_message,
        "agent_roles": run.agent_roles,
        "failure_code": run.failure_code,
        "failure_message": run.failure_message,
        "response_id": run.response_id,
        "confirmation_request_id": run.confirmation_request_id,
        "events": [_serialize_agent_run_event(event) for event in run.events.all()],
        "tool_executions": [
            _serialize_agent_run_tool_execution(execution)
            for execution in run.tool_executions.all()
        ],
    }


def _agent_run_summary(queryset):
    aggregate = queryset.aggregate(
        average_duration_ms=Avg("duration_ms"),
        total_tokens=Sum("total_tokens"),
        total_tool_calls=Sum("tool_call_count"),
        failed_tool_calls=Sum("failed_tool_count"),
        denied_tool_calls=Sum("denied_tool_count"),
    )
    total_runs = queryset.count()
    completed_runs = queryset.filter(status=AgentRun.Status.SUCCEEDED).count()
    return {
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "failed_runs": queryset.filter(status=AgentRun.Status.FAILED).count(),
        "blocked_runs": queryset.filter(status=AgentRun.Status.BLOCKED).count(),
        "escalated_runs": queryset.filter(status=AgentRun.Status.ESCALATED).count(),
        "awaiting_confirmation_runs": queryset.filter(
            status=AgentRun.Status.AWAITING_CONFIRMATION
        ).count(),
        "success_rate": round(completed_runs / total_runs * 100, 1) if total_runs else 0.0,
        "average_duration_ms": round(aggregate["average_duration_ms"] or 0),
        "total_tool_calls": aggregate["total_tool_calls"] or 0,
        "failed_tool_calls": aggregate["failed_tool_calls"] or 0,
        "denied_tool_calls": aggregate["denied_tool_calls"] or 0,
        "total_tokens": aggregate["total_tokens"],
    }


def _conversation_workflow_payload(conversation):
    pending_confirmation = get_pending_confirmation(conversation)
    return {
        "collaboration_plan": get_stored_plan_payload(conversation.context),
        "pending_confirmation": (
            serialize_confirmation(pending_confirmation) if pending_confirmation else None
        ),
        "recent_cases": [
            serialize_after_sales_case(after_sales_case)
            for after_sales_case in list_recent_cases(user=conversation.user)
        ],
    }


def _workflow_error_response(error: AfterSalesWorkflowError) -> Response:
    status_code = 404 if error.code in {"CONFIRMATION_NOT_FOUND", "CASE_NOT_FOUND", "ORDER_NOT_FOUND"} else 409
    return Response({"detail": error.message, "code": error.code}, status=status_code)


@extend_schema(
    summary="获取售后规则列表",
    tags=["售后 Agent"],
    responses=AfterSalesPolicySerializer(many=True),
)
class AfterSalesPolicyListView(APIView):
    """Return safe, static business rules used by the later Agent workflow."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        serializer = AfterSalesPolicySerializer(AFTER_SALES_POLICIES, many=True)
        return Response(serializer.data)


@extend_schema(
    summary="获取一条售后规则",
    tags=["售后 Agent"],
    responses=AfterSalesPolicySerializer,
)
class AfterSalesPolicyDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, policy_key, *args, **kwargs):
        policy = get_policy(policy_key)
        if policy is None:
            raise NotFound("未找到对应的售后规则。")
        return Response(AfterSalesPolicySerializer(policy).data)


@extend_schema(
    summary="发送一条售后 Agent 消息",
    tags=["售后 Agent"],
    request=ConversationMessageRequestSerializer,
    responses={200: AgentConversationTurnSerializer, 201: AgentConversationTurnSerializer},
)
class AgentConversationMessageView(APIView):
    """Create or continue an owner-scoped conversation and run the Agent turn."""

    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = ConversationMessageRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation_id = serializer.validated_data.get("conversation_id")
        if conversation_id:
            conversation = get_object_or_404(
                AgentConversation, id=conversation_id, user=request.user
            )
            created = False
        else:
            conversation = AgentConversation.objects.create(user=request.user)
            created = True

        try:
            result = run_agent_turn(
                user=request.user,
                conversation=conversation,
                message=serializer.validated_data["message"],
            )
        except (OpenAIConfigurationError, AfterSalesAgentUnavailableError):
            # A newly created conversation has no usable assistant turn after a failed
            # model request. Remove it so a later retry cannot inherit a half-finished turn.
            if created:
                conversation.delete()
            return Response(
                {"detail": "智能售后服务暂时不可用，请稍后重试。"}, status=503
            )
        except Exception:
            # Never let an unexpected Agent failure become Django's HTML debug page.
            # The frontend can then show a useful message and the user can retry.
            logger.exception("Unexpected after-sales Agent request failure")
            mark_active_agent_run_failed(
                conversation=conversation, error_code="AGENT_RUN_UNEXPECTED_ERROR"
            )
            if created:
                conversation.delete()
            return Response(
                {"detail": "售后助手暂时无法完成这次请求，请稍后重试。"}, status=503
            )

        return Response(
            {
                "conversation_id": conversation.id,
                "state": conversation.state,
                "assistant_message": result.assistant_message,
                "tool_calls": result.tool_calls,
                **_conversation_workflow_payload(conversation),
            },
            status=201 if created else 200,
        )


@extend_schema(
    summary="获取当前用户的售后 Agent 会话",
    tags=["售后 Agent"],
    responses=AgentConversationDetailSerializer,
)
class AgentConversationDetailView(APIView):
    """Return user-visible history only; tool inputs and results stay internal."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, conversation_id, *args, **kwargs):
        conversation = get_object_or_404(AgentConversation, id=conversation_id, user=request.user)
        messages = conversation.messages.filter(
            role__in=(AgentMessage.Role.USER, AgentMessage.Role.ASSISTANT)
        ).order_by("created_at")
        return Response(
            {
                "conversation_id": conversation.id,
                "state": conversation.state,
                "messages": AgentMessageHistorySerializer(messages, many=True).data,
                **_conversation_workflow_payload(conversation),
            }
        )


@extend_schema(
    summary="获取当前用户近期售后工单",
    tags=["售后 Agent"],
    responses=AfterSalesCaseResponseSerializer(many=True),
)
class AfterSalesCaseListView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        return Response(
            [serialize_after_sales_case(item) for item in list_recent_cases(user=request.user)]
        )


@extend_schema(
    summary="获取当前用户的售后通知",
    tags=["售后通知"],
    responses=AfterSalesNotificationListSerializer,
)
class AfterSalesNotificationListView(APIView):
    """Return only notifications belonging to the authenticated customer."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        notifications = list(
            AfterSalesNotification.objects.filter(user=request.user)
            .select_related("after_sales_case")
            .order_by("-created_at")[:50]
        )
        return Response(
            {
                "unread_count": AfterSalesNotification.objects.filter(
                    user=request.user, is_read=False
                ).count(),
                "notifications": [serialize_notification(item) for item in notifications],
            }
        )


@extend_schema(
    summary="将一条售后通知标记为已读",
    tags=["售后通知"],
    request=None,
    responses=AfterSalesNotificationSerializer,
)
class AfterSalesNotificationReadView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, notification_id, *args, **kwargs):
        notification = get_object_or_404(
            AfterSalesNotification, id=notification_id, user=request.user
        )
        notification = mark_notification_read(user=request.user, notification_id=notification.id)
        return Response(serialize_notification(notification))


@extend_schema(
    summary="将当前用户的售后通知全部标记为已读",
    tags=["售后通知"],
    request=None,
    responses=AfterSalesNotificationReadAllSerializer,
)
class AfterSalesNotificationReadAllView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        updated_count = mark_all_notifications_read(user=request.user)
        return Response(
            {
                "updated_count": updated_count,
                "read_at": timezone.now().isoformat(),
            }
        )


@extend_schema(
    summary="管理员：查看 Agent 运行总览",
    tags=["Agent 可观测性"],
    operation_id="staff_agent_run_list",
    responses=AgentRunListResponseSerializer,
)
class StaffAgentRunListView(APIView):
    """Return aggregate metrics and recent runs to staff only."""

    permission_classes = (IsAdminUser,)

    def get(self, request, *args, **kwargs):
        queryset = AgentRun.objects.select_related("user").order_by("-started_at")
        status = request.query_params.get("status") or None
        intent = request.query_params.get("intent") or None
        search = (request.query_params.get("search") or "").strip()[:100]
        valid_statuses = {value for value, _ in AgentRun.Status.choices}
        if status and status not in valid_statuses:
            return Response({"detail": "Agent 运行状态筛选条件无效。"}, status=400)
        if status:
            queryset = queryset.filter(status=status)
        if intent:
            queryset = queryset.filter(current_intent=intent)
        if search:
            queryset = queryset.filter(
                Q(input_message__icontains=search)
                | Q(user__username__icontains=search)
                | Q(response_id__icontains=search)
            )
        summary = _agent_run_summary(queryset)
        runs = list(queryset[:100])
        return Response(
            {
                "summary": summary,
                "runs": [_serialize_agent_run_list_item(run) for run in runs],
            }
        )


@extend_schema(
    summary="管理员：查看 Agent 单次运行详情",
    tags=["Agent 可观测性"],
    operation_id="staff_agent_run_detail",
    responses=AgentRunDetailSerializer,
)
class StaffAgentRunDetailView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request, run_id, *args, **kwargs):
        run = get_object_or_404(
            AgentRun.objects.select_related("user")
            .prefetch_related("events", "tool_executions"),
            id=run_id,
        )
        return Response(_serialize_agent_run_detail(run))


@extend_schema(
    summary="客服工作台：获取售后工单队列",
    tags=["客服工作台"],
    responses=StaffAfterSalesCaseSerializer(many=True),
)
class StaffAfterSalesCaseListView(APIView):
    """Return the staff-only work queue; regular users cannot access this endpoint."""

    permission_classes = (IsAdminUser,)

    def get(self, request, *args, **kwargs):
        status = request.query_params.get("status") or None
        priority = request.query_params.get("priority") or None
        search = (request.query_params.get("search") or "").strip()[:100] or None
        case_statuses = {value for value, _ in AfterSalesCase.Status.choices}
        case_priorities = {value for value, _ in AfterSalesCase.Priority.choices}
        if status and status not in case_statuses:
            return Response({"detail": "工单状态筛选条件无效。"}, status=400)
        if priority and priority not in case_priorities:
            return Response({"detail": "优先级筛选条件无效。"}, status=400)
        return Response(
            [
                serialize_staff_case(after_sales_case)
                for after_sales_case in list_staff_cases(
                    status=status,
                    priority=priority,
                    search=search,
                )
            ]
        )


@extend_schema(
    summary="客服工作台：获取售后工单详情",
    tags=["客服工作台"],
    responses=StaffAfterSalesCaseSerializer,
)
class StaffAfterSalesCaseDetailView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request, case_id, *args, **kwargs):
        after_sales_case = get_object_or_404(
            AfterSalesCase.objects.select_related("user", "order", "assigned_to", "conversation")
            .prefetch_related("order__items"),
            id=case_id,
        )
        return Response(serialize_staff_case(after_sales_case, include_conversation=True))

    def patch(self, request, case_id, *args, **kwargs):
        serializer = StaffAfterSalesCaseUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            after_sales_case = update_staff_case(
                staff_user=request.user,
                case_id=case_id,
                **serializer.validated_data,
            )
        except AfterSalesWorkflowError as exc:
            return _workflow_error_response(exc)
        return Response(serialize_staff_case(after_sales_case, include_conversation=True))


@extend_schema(
    summary="客服工作台：标记关联订单已发货",
    tags=["客服工作台"],
    responses=StaffAfterSalesCaseSerializer,
)
class StaffAfterSalesCaseShipOrderView(APIView):
    permission_classes = (IsAdminUser,)

    def post(self, request, case_id, *args, **kwargs):
        try:
            after_sales_case = ship_staff_case_order(staff_user=request.user, case_id=case_id)
        except AfterSalesWorkflowError as exc:
            return _workflow_error_response(exc)
        return Response(serialize_staff_case(after_sales_case, include_conversation=True))


@extend_schema(
    summary="客服工作台：标记关联订单已退款",
    tags=["客服工作台"],
    responses=StaffAfterSalesCaseSerializer,
)
class StaffAfterSalesCaseRefundOrderView(APIView):
    permission_classes = (IsAdminUser,)

    def post(self, request, case_id, *args, **kwargs):
        try:
            after_sales_case = refund_staff_case_order(staff_user=request.user, case_id=case_id)
        except AfterSalesWorkflowError as exc:
            return _workflow_error_response(exc)
        return Response(serialize_staff_case(after_sales_case, include_conversation=True))


@extend_schema(
    summary="客服工作台：获取订单发货队列",
    tags=["客服工作台"],
    responses=StaffOrderSerializer(many=True),
)
class StaffOrderListView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request, *args, **kwargs):
        status = request.query_params.get("status") or None
        search = (request.query_params.get("search") or "").strip()[:100] or None
        order_statuses = {value for value, _ in Order.Status.choices}
        if status and status not in order_statuses:
            return Response({"detail": "订单状态筛选条件无效。"}, status=400)
        return Response(
            [
                serialize_staff_order(order)
                for order in list_staff_orders(status=status, search=search)
            ]
        )


@extend_schema(
    summary="客服工作台：标记订单已发货",
    tags=["客服工作台"],
    responses=StaffOrderSerializer,
)
class StaffOrderShipView(APIView):
    permission_classes = (IsAdminUser,)

    def post(self, request, order_id, *args, **kwargs):
        try:
            order = ship_staff_order(staff_user=request.user, order_id=order_id)
        except AfterSalesWorkflowError as exc:
            return _workflow_error_response(exc)
        return Response(serialize_staff_order(order))


@extend_schema(
    summary="确认并执行一条售后申请",
    tags=["售后 Agent"],
    request=None,
    responses=ConfirmationExecutionSerializer,
)
class ConfirmationExecuteView(APIView):
    """The browser user's explicit confirmation is the only execution entry point."""

    permission_classes = (IsAuthenticated,)

    def post(self, request, confirmation_id, *args, **kwargs):
        try:
            execution = execute_confirmation(user=request.user, confirmation_id=confirmation_id)
        except AfterSalesWorkflowError as exc:
            return _workflow_error_response(exc)

        message = execution.confirmation.result.get("message", "售后申请已处理。")
        return Response(
            {
                "confirmation": serialize_confirmation(execution.confirmation),
                "after_sales_case": (
                    serialize_after_sales_case(execution.after_sales_case)
                    if execution.after_sales_case
                    else None
                ),
                "already_executed": execution.already_executed,
                "message": message,
            }
        )


@extend_schema(
    summary="取消一条待确认的售后申请",
    tags=["售后 Agent"],
    request=None,
    responses=ConfirmationRejectionSerializer,
)
class ConfirmationRejectView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, confirmation_id, *args, **kwargs):
        try:
            confirmation = reject_confirmation(user=request.user, confirmation_id=confirmation_id)
        except AfterSalesWorkflowError as exc:
            return _workflow_error_response(exc)

        return Response(
            {
                "confirmation": serialize_confirmation(confirmation),
                "message": confirmation.result.get("message", "已取消本次售后申请。"),
            }
        )
