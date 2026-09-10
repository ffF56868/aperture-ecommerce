"""Views for registration/OTP verification, login/logout, token refresh, and profile."""

from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenRefreshView as SimpleJWTTokenRefreshView

from .serializers import (
    ChangePasswordSerializer,
    ChangeUsernameSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    VerifyOTPSerializer,
)

User = get_user_model()


@extend_schema(
    summary="Register — submit username/phone/password to create an account",
    tags=["Authentication"],
    responses={201: OpenApiResponse(description="Account created")},
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "otp_request"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "detail": "注册成功。",
                "phone_number": serializer.validated_data["phone_number"],
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    summary="Verify OTP (step 3) — unlocks the account and marks the phone as verified",
    tags=["Authentication"],
)
class VerifyOTPView(generics.GenericAPIView):
    serializer_class = VerifyOTPSerializer
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "otp_verify"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserProfileSerializer(user).data, status=status.HTTP_200_OK)


@extend_schema(summary="Login with username + password", tags=["Authentication"])
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(summary="Logout — blacklists the given refresh token", tags=["Authentication"])
class LogoutView(generics.GenericAPIView):
    serializer_class = LogoutSerializer
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_205_RESET_CONTENT)


@extend_schema(summary="Refresh an access token", tags=["Authentication"])
class TokenRefreshView(SimpleJWTTokenRefreshView):
    """Thin wrapper purely so drf-spectacular tags it under 'Authentication'."""


@extend_schema(summary="Retrieve the authenticated user's profile", tags=["Profile"])
class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user


@extend_schema(summary="Change the authenticated user's username", tags=["Profile"])
class ChangeUsernameView(generics.UpdateAPIView):
    serializer_class = ChangeUsernameSerializer
    permission_classes = (IsAuthenticated,)
    http_method_names = ["patch"]

    def get_object(self):
        return self.request.user


@extend_schema(summary="Change the authenticated user's password", tags=["Profile"])
class ChangePasswordView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "密码更新成功。"}, status=status.HTTP_200_OK)
