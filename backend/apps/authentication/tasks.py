"""Async tasks: OTP delivery via SMS (mocked provider), invoice generation, cleanup."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_otp_sms(self, phone_number: str, code: str):
    """
    Send an OTP code to a phone number via SMS.

    This is a mock provider integration point: swap the body for a real
    provider call (Twilio, Kavenegar, etc.) in production. Logging the send
    here keeps local/dev environments fully functional without credentials.
    """
    try:
        logger.info("Sending OTP %s to %s (mock SMS provider)", code, phone_number)
        # e.g. twilio_client.messages.create(to=phone_number, body=f"Your code is {code}")
        return {"phone_number": phone_number, "status": "sent"}
    except Exception as exc:  # pragma: no cover - defensive retry path
        logger.exception("Failed to send OTP to %s", phone_number)
        raise self.retry(exc=exc) from exc


@shared_task
def cleanup_expired_otp_records():
    """Periodic housekeeping: remove stale unverified OTP audit rows older than 7 days."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import OTPVerification

    cutoff = timezone.now() - timedelta(days=7)
    deleted_count, _ = OTPVerification.objects.filter(
        is_verified=False, created_at__lt=cutoff
    ).delete()
    logger.info("Cleaned up %s expired OTP records", deleted_count)
    return deleted_count
