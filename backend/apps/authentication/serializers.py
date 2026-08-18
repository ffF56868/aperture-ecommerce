"""Serializers for registration/OTP verification, login, and profile management."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from core.utils import generate_otp_code, get_cached_otp, store_otp

from .models import OTPVerification

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """
    Step 1 of registration: username + phone number + password.

    Creates an unverified user (or reuses an existing unverified one to
    support OTP resend) and dispatches a fresh OTP via Celery.
    """

    username = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_username(self, value):
        existing = User.objects.filter(username=value).first()
        if existing and existing.is_phone_verified:
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_phone_number(self, value):
        existing = User.objects.filter(phone_number=value).first()
        if existing and existing.is_phone_verified:
            raise serializers.ValidationError("This phone number is already registered.")
        return value

    def create(self, validated_data):
        username = validated_data["username"]
        phone_number = validated_data["phone_number"]
        password = validated_data["password"]

        user, _ = User.objects.update_or_create(
            phone_number=phone_number,
            defaults={"username": username, "is_phone_verified": False},
        )
        user.set_password(password)
        user.save(update_fields=["password", "username", "is_phone_verified"])

        code = generate_otp_code()
        store_otp(str(phone_number), code)
        OTPVerification.objects.create(
            user=user,
            phone_number=phone_number,
            purpose=OTPVerification.Purpose.REGISTRATION,
        )

        from .tasks import send_otp_sms

        send_otp_sms.delay(str(phone_number), code)
        return user


class VerifyOTPSerializer(serializers.Serializer):
    """Step 3 of registration: verify the OTP code sent to the phone number."""

    phone_number = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6, min_length=4)

    def validate(self, attrs):
        phone_number = attrs["phone_number"]
        cached_code = get_cached_otp(str(phone_number))

        record = (
            OTPVerification.objects.filter(phone_number=phone_number, is_verified=False)
            .order_by("-created_at")
            .first()
        )

        if cached_code is None:
            raise serializers.ValidationError("The OTP code has expired. Please request a new one.")

        if record and record.attempt_count >= 5:
            raise serializers.ValidationError(
                "Too many incorrect attempts. Please request a new code."
            )

        if cached_code != attrs["code"]:
            if record:
                record.attempt_count += 1
                record.save(update_fields=["attempt_count"])
            raise serializers.ValidationError("Invalid OTP code.")

        attrs["_record"] = record
        return attrs

    def save(self, **kwargs):
        from django.utils import timezone

        from core.utils import clear_otp

        phone_number = self.validated_data["phone_number"]
        user = User.objects.get(phone_number=phone_number)
        user.is_phone_verified = True
        user.save(update_fields=["is_phone_verified"])

        record = self.validated_data.get("_record")
        if record:
            record.is_verified = True
            record.verified_at = timezone.now()
            record.save(update_fields=["is_verified", "verified_at"])

        clear_otp(str(phone_number))
        return user


class LoginSerializer(serializers.Serializer):
    """Authenticate with username + password; returns JWT access/refresh tokens."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = User.objects.filter(username=attrs["username"]).first()
        if user is None or not user.check_password(attrs["password"]):
            raise serializers.ValidationError("Invalid username or password.")
        if not user.is_phone_verified:
            raise serializers.ValidationError("Please verify your phone number before logging in.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")

        attrs["user"] = user
        return attrs

    def to_representation(self, instance):
        user = instance["user"]
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserProfileSerializer(user).data,
        }


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def save(self, **kwargs):
        try:
            token = RefreshToken(self.validated_data["refresh"])
            token.blacklist()
        except Exception as exc:  # noqa: BLE001
            raise serializers.ValidationError(
                "Invalid or already-blacklisted refresh token."
            ) from exc


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "phone_number", "email", "is_phone_verified", "created_at")
        read_only_fields = fields


class ChangeUsernameSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username",)

    def validate_username(self, value):
        qs = User.objects.filter(username=value).exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This username is already taken.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
