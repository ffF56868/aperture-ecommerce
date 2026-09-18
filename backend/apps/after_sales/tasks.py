"""Celery delivery tasks for the after-sales notification center."""

import logging

from celery import shared_task
from django.utils import timezone

from .knowledge import KnowledgeBaseError, index_document
from .models import AfterSalesNotification, KnowledgeDocument

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def index_after_sales_knowledge_document(self, document_id: str, force: bool = False):
    """Build embeddings off the request thread and persist the indexing state."""

    try:
        document = KnowledgeDocument.objects.get(id=document_id)
    except KnowledgeDocument.DoesNotExist:
        return {"status": "missing", "document_id": document_id}
    try:
        chunks_indexed = index_document(document, force=force)
    except KnowledgeBaseError as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        logger.exception("Knowledge indexing failed for %s", document_id)
        return {"status": "failed", "document_id": document_id, "error": str(exc)}
    return {"status": "ready", "document_id": document_id, "chunks_indexed": chunks_indexed}


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_after_sales_notification_email(self, notification_id: str):
    """Simulate email delivery and persist the delivery outcome for auditability."""

    try:
        notification = AfterSalesNotification.objects.select_related("user").get(
            id=notification_id
        )
    except AfterSalesNotification.DoesNotExist:
        logger.warning("After-sales notification %s no longer exists", notification_id)
        return {"status": "missing", "notification_id": notification_id}

    if notification.email_status == AfterSalesNotification.EmailStatus.SENT:
        return {"status": "already_sent", "notification_id": notification_id}

    email = (notification.user.email or "").strip()
    if not email:
        notification.email_status = AfterSalesNotification.EmailStatus.SKIPPED
        notification.email_error = "用户未填写邮箱，保留站内通知。"
        notification.save(update_fields=["email_status", "email_error", "updated_at"])
        logger.info(
            "Skipped mock after-sales email for %s: user %s has no email",
            notification.id,
            notification.user_id,
        )
        return {"status": "skipped", "notification_id": notification_id}

    try:
        logger.info(
            "Mock after-sales email sent to %s: [%s] %s",
            email,
            notification.title,
            notification.message,
        )
        notification.email_status = AfterSalesNotification.EmailStatus.SENT
        notification.email_sent_at = timezone.now()
        notification.email_error = ""
        notification.save(
            update_fields=["email_status", "email_sent_at", "email_error", "updated_at"]
        )
        return {"status": "sent", "notification_id": notification_id, "email": email}
    except Exception as exc:  # pragma: no cover - defensive retry path
        notification.email_status = AfterSalesNotification.EmailStatus.FAILED
        notification.email_error = str(exc)[:255]
        notification.save(update_fields=["email_status", "email_error", "updated_at"])
        logger.exception("Failed to send mock after-sales email %s", notification_id)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def extract_conversation_memories(self, conversation_id: str):
    """Extract user preferences and conversation summary using LLM.

    This task runs asynchronously after a conversation turn completes.
    It analyzes the conversation history and extracts:
    - User preferences (LONG_TERM memory)
    - Conversation summary (EPISODIC memory, 60-day TTL)

    Args:
        conversation_id: UUID of the conversation to analyze
    """
    from .memory import MemoryError, extract_memories_from_conversation

    try:
        result = extract_memories_from_conversation(conversation_id)
        logger.info(
            "Memory extraction completed for conversation %s: %s",
            conversation_id,
            result,
        )
        return result
    except MemoryError as exc:
        logger.warning(
            "Memory extraction failed for conversation %s: %s",
            conversation_id,
            exc,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception(
            "Unexpected error during memory extraction for conversation %s",
            conversation_id,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        return {"error": str(exc)}
