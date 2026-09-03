"""Notification creation and delivery orchestration for after-sales cases."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import AfterSalesCase, AfterSalesNotification


EVENT_COPY = {
    AfterSalesNotification.EventType.CASE_CREATED: (
        "售后工单已创建",
        "你的售后工单 {case_number} 已创建，当前状态为待人工审核。",
    ),
    AfterSalesNotification.EventType.CASE_APPROVED: (
        "售后工单审核通过",
        "你的售后工单 {case_number} 已审核通过。{note}",
    ),
    AfterSalesNotification.EventType.CASE_REJECTED: (
        "售后工单审核未通过",
        "你的售后工单 {case_number} 审核未通过。{note}",
    ),
    AfterSalesNotification.EventType.NEED_CUSTOMER_INFO: (
        "请补充售后资料",
        "你的售后工单 {case_number} 需要补充资料。{note}",
    ),
}


def _event_note(after_sales_case: AfterSalesCase) -> str:
    note = (after_sales_case.staff_note or "").strip()
    return f"客服备注：{note}" if note else "请打开售后助手查看详情。"


def create_case_notification(
    after_sales_case: AfterSalesCase,
    event_type: str,
) -> tuple[AfterSalesNotification, bool]:
    """Create one idempotent notification and enqueue its mock email after commit."""

    if event_type not in EVENT_COPY:
        raise ValueError(f"Unsupported after-sales notification event: {event_type}")

    title, message_template = EVENT_COPY[event_type]
    notification, created = AfterSalesNotification.objects.get_or_create(
        after_sales_case=after_sales_case,
        event_type=event_type,
        defaults={
            "user_id": after_sales_case.user_id,
            "title": title,
            "message": message_template.format(
                case_number=after_sales_case.case_number,
                note=_event_note(after_sales_case),
            ),
            "action_url": "/after-sales",
        },
    )
    if created:
        notification_id = str(notification.id)

        def enqueue_email() -> None:
            from .tasks import send_after_sales_notification_email

            send_after_sales_notification_email.delay(notification_id)

        transaction.on_commit(enqueue_email)
    return notification, created


def serialize_notification(notification: AfterSalesNotification) -> dict[str, Any]:
    """Return only fields safe for the notification owner."""

    return {
        "id": str(notification.id),
        "event_type": notification.event_type,
        "title": notification.title,
        "message": notification.message,
        "action_url": notification.action_url,
        "is_read": notification.is_read,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "email_status": notification.email_status,
        "created_at": notification.created_at.isoformat(),
        "case_number": (
            notification.after_sales_case.case_number if notification.after_sales_case else None
        ),
    }


def mark_notification_read(*, user: Any, notification_id: Any) -> AfterSalesNotification:
    notification = AfterSalesNotification.objects.get(id=notification_id, user=user)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return notification


def mark_all_notifications_read(*, user: Any) -> int:
    return AfterSalesNotification.objects.filter(user=user, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )
