"""Custom User model: username + E.164 phone number + OTP verification flag."""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from core.mixins import TimeStampedMixin


class UserManager(BaseUserManager):
    """Manager for the custom User model, keyed on username + phone number."""

    use_in_migrations = True

    def _create_user(self, username, phone_number, password, **extra_fields):
        if not username:
            raise ValueError("Users must have a username.")
        if not phone_number:
            raise ValueError("Users must have a phone number.")

        user = self.model(username=username, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, phone_number, password, **extra_fields)

    def create_superuser(self, username, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_phone_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(username, phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedMixin):
    """
    Custom user model.

    Authenticates via username + password. Phone number is the channel used
    for OTP-based verification during registration.
    """

    username_validator = UnicodeUsernameValidator()

    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[username_validator],
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
    )
    phone_number = PhoneNumberField(
        unique=True, help_text="E.164 formatted phone number, e.g. +14155552671"
    )
    email = models.EmailField(blank=True, null=True)

    is_phone_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["phone_number"]

    class Meta:
        db_table = "auth_users"
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ("-created_at",)

    def __str__(self):
        return self.username


class OTPVerification(TimeStampedMixin):
    """
    Audit trail of OTP verification attempts.

    The live/pending OTP code itself is cached in Redis with a short TTL
    (see core.utils.store_otp); this table records verification outcomes
    for auditing and rate-limit analytics, not the raw code.
    """

    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Registration"
        PASSWORD_RESET = "password_reset", "Password Reset"

    user = models.ForeignKey(
        "authentication.User",
        on_delete=models.CASCADE,
        related_name="otp_verifications",
        null=True,
        blank=True,
    )
    phone_number = PhoneNumberField()
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.REGISTRATION)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "auth_otp_verifications"
        verbose_name = "OTP Verification"
        verbose_name_plural = "OTP Verifications"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["phone_number", "purpose"])]

    def __str__(self):
        return f"OTP for {self.phone_number} ({self.purpose})"
