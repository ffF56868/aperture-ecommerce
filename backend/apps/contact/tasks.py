"""Async tasks for the contact app."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def notify_new_contact_inquiry(inquiry_id: int):
    """
    Notify staff of a new contact inquiry.

    Mock notification: logs the event. Swap for a real email/Slack integration
    in production (e.g. django.core.mail.send_mail to a support inbox).
    """
    from .models import ContactInquiry

    try:
        inquiry = ContactInquiry.objects.get(id=inquiry_id)
    except ContactInquiry.DoesNotExist:
        logger.warning("Contact inquiry %s no longer exists", inquiry_id)
        return

    logger.info(
        "New contact inquiry from %s <%s>: %s", inquiry.full_name, inquiry.email, inquiry.subject
    )
