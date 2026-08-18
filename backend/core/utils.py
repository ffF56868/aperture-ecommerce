"""Shared utility helpers used across the backend."""

import secrets
import string

from django.conf import settings
from django.core.cache import cache


def generate_otp_code(length: int | None = None) -> str:
    """Generate a cryptographically secure numeric OTP code."""
    length = length or settings.OTP_LENGTH
    return "".join(secrets.choice(string.digits) for _ in range(length))


def otp_cache_key(phone_number: str) -> str:
    return f"otp:{phone_number}"


def otp_attempts_cache_key(phone_number: str) -> str:
    return f"otp:attempts:{phone_number}"


def store_otp(phone_number: str, code: str) -> None:
    """Cache an OTP code for a phone number with the configured expiry."""
    cache.set(otp_cache_key(phone_number), code, timeout=settings.OTP_EXPIRY_SECONDS)


def get_cached_otp(phone_number: str) -> str | None:
    return cache.get(otp_cache_key(phone_number))


def clear_otp(phone_number: str) -> None:
    cache.delete(otp_cache_key(phone_number))


def build_error_response(detail: str, code: str = "error") -> dict:
    """Consistent shape for error payloads returned by the API."""
    return {"detail": detail, "code": code}
