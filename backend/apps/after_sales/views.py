"""API endpoints for after-sales rules and the controlled Agent conversation."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .agent_service import AfterSalesAgentUnavailableError, run_agent_turn
from .models import AgentConversation, AgentMessage
from .openai_client import OpenAIConfigurationError
from .policies import AFTER_SALES_POLICIES, get_policy
from .serializers import (
    AfterSalesPolicySerializer,
    AgentConversationDetailSerializer,
    AgentConversationTurnSerializer,
    AgentMessageHistorySerializer,
    AfterSalesCaseResponseSerializer,
    ConfirmationExecutionSerializer,
    ConfirmationRejectionSerializer,
    ConversationMessageRequestSerializer,
)
from .workflow import (
    AfterSalesWorkflowError,
    execute_confirmation,
    get_pending_confirmation,
    list_recent_cases,
    reject_confirmation,
    serialize_after_sales_case,
    serialize_confirmation,
)


def _conversation_workflow_payload(conversation):
    pending_confirmation = get_pending_confirmation(conversation)
    return {
        "pending_confirmation": (
            serialize_confirmation(pending_confirmation) if pending_confirmation else None
        ),
        "recent_cases": [
            serialize_after_sales_case(after_sales_case)
            for after_sales_case in list_recent_cases(user=conversation.user)
        ],
    }


def _workflow_error_response(error: AfterSalesWorkflowError) -> Response:
    status_code = 404 if error.code == "CONFIRMATION_NOT_FOUND" else 409
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
