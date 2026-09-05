"""API endpoints for after-sales rules and the controlled Agent conversation."""

import logging
import uuid

from django.db import transaction
from django.db.models import Avg, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart_orders.models import Order
from apps.products.models import Category, Product

from .agent_service import (
    AfterSalesAgentUnavailableError,
    mark_active_agent_run_failed,
    run_agent_turn,
)
from .collaboration import get_stored_plan_payload
from .evaluation import AfterSalesAgentEvaluator
from .models import (
    AfterSalesCase,
    AfterSalesNotification,
    AgentConversation,
    AgentEvaluationCaseResult,
    AgentEvaluationRun,
    AgentMessage,
    AgentRun,
    AgentRunEvent,
    ToolExecution,
    KnowledgeDocument,
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
    AgentEvaluationRunDetailSerializer,
    AgentEvaluationRunListResponseSerializer,
    StaffKnowledgeDocumentListResponseSerializer,
    StaffKnowledgeDocumentSerializer,
    StaffKnowledgeDocumentWriteSerializer,
    StaffKnowledgeSearchSerializer,
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
from .knowledge import KnowledgeBaseError, search_after_sales_knowledge
from .knowledge_ingest import KnowledgeIngestError, extract_uploaded_file, extract_webpage, source_type_for
from .tasks import index_after_sales_knowledge_document
from .vector_store import MilvusUnavailable, delete_document_vectors

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


def _serialize_evaluation_run_list_item(evaluation_run):
    return {
        "id": evaluation_run.id,
        "status": evaluation_run.status,
        "status_label": evaluation_run.get_status_display(),
        "trigger": evaluation_run.trigger,
        "trigger_label": evaluation_run.get_trigger_display(),
        "mode": evaluation_run.mode,
        "started_at": evaluation_run.started_at,
        "finished_at": evaluation_run.finished_at,
        "total_cases": evaluation_run.total_cases,
        "passed_cases": evaluation_run.passed_cases,
        "failed_cases": evaluation_run.failed_cases,
        "average_response_ms": evaluation_run.average_response_ms,
    }


def _evaluation_rate(passed, total):
    return round(passed / total * 100, 1) if total else 0.0


def _serialize_evaluation_metrics(evaluation_run):
    def metric(passed, total):
        return {
            "passed": passed,
            "total": total,
            "failed": total - passed,
            "rate": _evaluation_rate(passed, total),
        }

    return {
        "intent_recognition": metric(evaluation_run.intent_correct, evaluation_run.intent_total),
        "tool_selection": metric(
            evaluation_run.tool_selection_correct, evaluation_run.tool_selection_total
        ),
        "parameter_correctness": metric(
            evaluation_run.parameter_correct, evaluation_run.parameter_total
        ),
        "unauthorized_interception": metric(
            evaluation_run.unauthorized_blocked, evaluation_run.unauthorized_total
        ),
        "dangerous_interception": metric(
            evaluation_run.dangerous_blocked, evaluation_run.dangerous_total
        ),
        "average_response_time": {
            "value": evaluation_run.average_response_ms,
            "unit": "ms",
        },
        "human_handoff": metric(
            evaluation_run.human_escalated, evaluation_run.human_escalation_total
        ),
        "failure": {
            "failed": evaluation_run.failure_total,
            "total": evaluation_run.total_cases,
            "rate": _evaluation_rate(evaluation_run.failure_total, evaluation_run.total_cases),
        },
    }


def _serialize_evaluation_case_result(case_result):
    return {
        "id": case_result.id,
        "case_id": case_result.case_id,
        "category": case_result.category,
        "description": case_result.description,
        "message": case_result.message,
        "expected_intent": case_result.expected_intent,
        "actual_intent": case_result.actual_intent,
        "expected_tools": case_result.expected_tools,
        "actual_tools": case_result.actual_tools,
        "expected_arguments": case_result.expected_arguments,
        "actual_arguments": case_result.actual_arguments,
        "passed": case_result.passed,
        "intent_passed": case_result.intent_passed,
        "tool_selection_passed": case_result.tool_selection_passed,
        "parameter_applicable": case_result.parameter_applicable,
        "parameter_passed": case_result.parameter_passed,
        "authorization_passed": case_result.authorization_passed,
        "unauthorized_case": case_result.unauthorized_case,
        "unauthorized_blocked": case_result.unauthorized_blocked,
        "dangerous_case": case_result.dangerous_case,
        "dangerous_blocked": case_result.dangerous_blocked,
        "response_compliance_passed": case_result.response_compliance_passed,
        "human_escalated": case_result.human_escalated,
        "failed": case_result.failed,
        "response_time_ms": case_result.response_time_ms,
        "actual_error_codes": case_result.actual_error_codes,
        "assistant_message": case_result.assistant_message,
        "failures": case_result.failures,
    }


def _serialize_evaluation_run_detail(evaluation_run):
    return {
        **_serialize_evaluation_run_list_item(evaluation_run),
        "metrics": _serialize_evaluation_metrics(evaluation_run),
        "cases": [
            _serialize_evaluation_case_result(case_result)
            for case_result in evaluation_run.case_results.all()
        ],
        "error_message": evaluation_run.error_message,
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
    summary="管理员：查看 Agent 评测批次",
    tags=["Agent 评测"],
    operation_id="staff_agent_evaluation_list",
    responses=AgentEvaluationRunListResponseSerializer,
)
class StaffAgentEvaluationListView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request, *args, **kwargs):
        queryset = AgentEvaluationRun.objects.order_by("-started_at")
        latest = queryset.first()
        return Response(
            {
                "summary": {
                    "total_runs": queryset.count(),
                    "latest_run_id": latest.id if latest else None,
                    "latest_started_at": latest.started_at if latest else None,
                },
                "runs": [_serialize_evaluation_run_list_item(item) for item in queryset[:30]],
            }
        )


@extend_schema(
    summary="管理员：查看 Agent 评测结果",
    tags=["Agent 评测"],
    operation_id="staff_agent_evaluation_detail",
    responses=AgentEvaluationRunDetailSerializer,
)
class StaffAgentEvaluationDetailView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request, evaluation_run_id, *args, **kwargs):
        evaluation_run = get_object_or_404(
            AgentEvaluationRun.objects.prefetch_related("case_results"), id=evaluation_run_id
        )
        return Response(_serialize_evaluation_run_detail(evaluation_run))


@extend_schema(
    summary="管理员：运行 Agent 评测",
    tags=["Agent 评测"],
    operation_id="staff_agent_evaluation_run",
    responses=AgentEvaluationRunDetailSerializer,
)
class StaffAgentEvaluationRunView(APIView):
    permission_classes = (IsAdminUser,)

    def post(self, request, *args, **kwargs):
        report = AfterSalesAgentEvaluator().run(trigger=AgentEvaluationRun.Trigger.DASHBOARD)
        evaluation_run = get_object_or_404(
            AgentEvaluationRun.objects.prefetch_related("case_results"), id=report.evaluation_run_id
        )
        return Response(_serialize_evaluation_run_detail(evaluation_run), status=201)


def _serialize_knowledge_document(document):
    file_url = None
    file_name = ""
    if document.file:
        file_name = document.file.name.rsplit("/", 1)[-1]
        try:
            file_url = document.file.url
        except ValueError:
            file_url = None
    product = (
        {"id": str(document.product_id), "name": document.product.name}
        if document.product_id and document.product
        else None
    )
    product_category = (
        {"id": str(document.product_category_id), "name": document.product_category.name}
        if document.product_category_id and document.product_category
        else None
    )
    uploaded_by = (
        {"id": document.uploaded_by_id, "username": document.uploaded_by.username}
        if document.uploaded_by_id and document.uploaded_by
        else None
    )
    return {
        "id": document.id,
        "title": document.title,
        "slug": document.slug,
        "category": document.category,
        "source_label": document.source_label,
        "source_type": document.source_type,
        "source_type_label": document.get_source_type_display(),
        "source_url": document.source_url,
        "file_name": file_name,
        "file_url": file_url,
        "content_preview": document.content[:320],
        "product": product,
        "product_category": product_category,
        "is_published": document.is_published,
        "index_status": document.index_status,
        "index_status_label": document.get_index_status_display(),
        "index_error": document.index_error,
        "chunk_count": document.chunk_count,
        "indexed_at": document.indexed_at,
        "uploaded_by": uploaded_by,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _queue_knowledge_index(document, *, force: bool = False) -> None:
    document.index_status = document.IndexStatus.PENDING
    document.index_error = ""
    document.save(update_fields=["index_status", "index_error", "updated_at"])

    def dispatch() -> None:
        try:
            index_after_sales_knowledge_document.delay(str(document.id), force=force)
        except Exception as exc:  # pragma: no cover - depends on broker availability
            logger.exception("Could not queue knowledge indexing for %s", document.id)
            KnowledgeDocument.objects.filter(id=document.id).update(
                index_status=KnowledgeDocument.IndexStatus.FAILED,
                index_error="索引任务暂时无法排队，请检查 Celery 和 Redis。",
                updated_at=timezone.now(),
            )

    transaction.on_commit(dispatch)


def _knowledge_scope_objects(validated_data):
    product_id = validated_data.pop("product_id", None)
    category_id = validated_data.pop("product_category_id", None)
    product = Product.objects.filter(id=product_id).first() if product_id else None
    category = Category.objects.filter(id=category_id).first() if category_id else None
    if product_id and product is None:
        raise ValueError("适用商品不存在。")
    if category_id and category is None:
        raise ValueError("适用商品分类不存在。")
    return product, category


@extend_schema(
    summary="管理员：管理售后知识文档",
    tags=["售后知识库"],
    request=StaffKnowledgeDocumentWriteSerializer,
    responses=StaffKnowledgeDocumentListResponseSerializer,
)
class StaffKnowledgeDocumentListView(APIView):
    permission_classes = (IsAdminUser,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get(self, request, *args, **kwargs):
        queryset = KnowledgeDocument.objects.select_related(
            "product", "product_category", "uploaded_by"
        ).order_by("category", "title")
        status = request.query_params.get("status")
        search = (request.query_params.get("search") or "").strip()[:100]
        if status:
            if status not in {value for value, _ in KnowledgeDocument.IndexStatus.choices}:
                return Response({"detail": "索引状态筛选条件无效。"}, status=400)
            queryset = queryset.filter(index_status=status)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(source_label__icontains=search)
                | Q(category__icontains=search)
                | Q(content__icontains=search)
            )
        return Response(
            {
                "summary": {
                    "total": queryset.count(),
                    "ready": queryset.filter(index_status=KnowledgeDocument.IndexStatus.READY).count(),
                    "pending": queryset.filter(index_status=KnowledgeDocument.IndexStatus.PENDING).count(),
                    "processing": queryset.filter(index_status=KnowledgeDocument.IndexStatus.PROCESSING).count(),
                    "failed": queryset.filter(index_status=KnowledgeDocument.IndexStatus.FAILED).count(),
                },
                "documents": [_serialize_knowledge_document(item) for item in queryset],
            }
        )

    def post(self, request, *args, **kwargs):
        serializer = StaffKnowledgeDocumentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        uploaded_file = data.pop("file", None) or request.FILES.get("file")
        source_url = data.get("source_url", "")
        raw_content = data.get("content", "")
        try:
            source_type = source_type_for(
                uploaded_file=uploaded_file, source_url=source_url, content=raw_content
            )
            page_title = ""
            if uploaded_file is not None:
                content, _ = extract_uploaded_file(uploaded_file)
            elif source_url:
                content, page_title = extract_webpage(source_url)
            else:
                content = raw_content.strip()
            product, product_category = _knowledge_scope_objects(data)
        except (KnowledgeIngestError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=400)
        title = (data.get("title") or page_title or getattr(uploaded_file, "name", "")).strip()
        if not title:
            return Response({"detail": "请填写文档标题。"}, status=400)
        slug = (data.get("slug") or slugify(title, allow_unicode=True)).strip()[:100]
        if not slug:
            slug = f"knowledge-{uuid.uuid4().hex[:12]}"
        if KnowledgeDocument.objects.filter(slug=slug).exists():
            slug = f"{slug[:86]}-{uuid.uuid4().hex[:12]}"
        document = KnowledgeDocument.objects.create(
            title=title,
            slug=slug,
            category=data.get("category", "售后规则"),
            source_label=data.get("source_label") or title,
            content=content,
            source_type=source_type,
            file=uploaded_file,
            source_url=source_url,
            product=product,
            product_category=product_category,
            is_published=data.get("is_published", True),
            uploaded_by=request.user,
            index_status=KnowledgeDocument.IndexStatus.PENDING,
        )
        _queue_knowledge_index(document)
        document = KnowledgeDocument.objects.select_related(
            "product", "product_category", "uploaded_by"
        ).get(id=document.id)
        return Response(_serialize_knowledge_document(document), status=202)


@extend_schema(
    summary="管理员：更新售后知识文档",
    tags=["售后知识库"],
    request=StaffKnowledgeDocumentWriteSerializer,
    responses=StaffKnowledgeDocumentSerializer,
)
class StaffKnowledgeDocumentDetailView(APIView):
    permission_classes = (IsAdminUser,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get(self, request, document_id, *args, **kwargs):
        document = get_object_or_404(
            KnowledgeDocument.objects.select_related("product", "product_category", "uploaded_by"),
            id=document_id,
        )
        return Response(_serialize_knowledge_document(document))

    def patch(self, request, document_id, *args, **kwargs):
        document = get_object_or_404(KnowledgeDocument, id=document_id)
        serializer = StaffKnowledgeDocumentWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        uploaded_file = data.pop("file", None) or request.FILES.get("file")
        content_changed = any(key in data for key in ("content", "source_url", "product_id", "product_category_id"))
        try:
            if uploaded_file is not None:
                document.content, _ = extract_uploaded_file(uploaded_file)
                if document.file:
                    document.file.delete(save=False)
                document.file = uploaded_file
                document.source_url = ""
                document.source_type = KnowledgeDocument.SourceType.FILE
                content_changed = True
            elif "source_url" in data and data["source_url"]:
                document.content, page_title = extract_webpage(data["source_url"])
                if document.file:
                    document.file.delete(save=False)
                document.file = None
                document.source_type = KnowledgeDocument.SourceType.WEBPAGE
                if "title" not in data and page_title:
                    document.title = page_title
                content_changed = True
            elif "content" in data:
                document.content = data["content"].strip()
                if document.file:
                    document.file.delete(save=False)
                document.file = None
                document.source_url = ""
                document.source_type = KnowledgeDocument.SourceType.TEXT
            if "source_url" in data:
                document.source_url = data["source_url"]
            product, product_category = _knowledge_scope_objects(data)
            if "product_id" in serializer.validated_data:
                document.product = product
            if "product_category_id" in serializer.validated_data:
                document.product_category = product_category
        except (KnowledgeIngestError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=400)
        for field in ("title", "category", "source_label", "slug", "is_published"):
            if field in data:
                setattr(document, field, data[field])
        if "source_label" in data and not document.source_label:
            document.source_label = document.title
        if not document.title.strip() or not document.content.strip():
            return Response({"detail": "标题和知识内容不能为空。"}, status=400)
        document.save()
        if content_changed:
            _queue_knowledge_index(document, force=True)
        document = KnowledgeDocument.objects.select_related("product", "product_category", "uploaded_by").get(id=document.id)
        return Response(_serialize_knowledge_document(document))

    def delete(self, request, document_id, *args, **kwargs):
        document = get_object_or_404(KnowledgeDocument, id=document_id)
        try:
            if settings.AFTER_SALES_VECTOR_BACKEND.lower() == "milvus":
                delete_document_vectors(str(document.id))
        except MilvusUnavailable:
            logger.warning("Milvus old vectors could not be removed for %s", document.id)
        if document.file:
            document.file.delete(save=False)
        document.delete()
        return Response(status=204)


@extend_schema(
    summary="管理员：重建售后知识文档索引",
    tags=["售后知识库"],
    request=None,
    responses=StaffKnowledgeDocumentSerializer,
)
class StaffKnowledgeDocumentReindexView(APIView):
    permission_classes = (IsAdminUser,)

    def post(self, request, document_id, *args, **kwargs):
        document = get_object_or_404(KnowledgeDocument, id=document_id)
        _queue_knowledge_index(document, force=True)
        document.refresh_from_db()
        return Response(_serialize_knowledge_document(document), status=202)


@extend_schema(
    summary="管理员：测试售后知识检索",
    tags=["售后知识库"],
    request=StaffKnowledgeSearchSerializer,
    responses=serializers.DictField(),
)
class StaffKnowledgeSearchView(APIView):
    """Let staff verify retrieval and citations without exposing this to customers."""

    permission_classes = (IsAdminUser,)

    def post(self, request, *args, **kwargs):
        serializer = StaffKnowledgeSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = search_after_sales_knowledge(
                data["question"],
                limit=data.get("limit", 3),
                product_id=str(data["product_id"]) if data.get("product_id") else None,
                category_id=str(data["category_id"]) if data.get("category_id") else None,
            )
        except KnowledgeBaseError as exc:
            return Response({"detail": str(exc)}, status=503)
        return Response(
            {
                "question": data["question"],
                "matches": result.matches,
                "requires_human_escalation": result.requires_human_escalation,
                "message": result.message,
            }
        )


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
