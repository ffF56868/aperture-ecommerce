"""Routes: /api/v1/auth/... and /api/v1/profile/..."""

from django.urls import path

from .views import LoginView, LogoutView, RegisterView, TokenRefreshView, VerifyOTPView

app_name = "authentication"

urlpatterns = [
    # /api/v1/auth/...
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]
