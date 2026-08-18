"""Routes: /api/v1/profile/..."""

from django.urls import path

from .views import ChangePasswordView, ChangeUsernameView, ProfileView

app_name = "profile"

urlpatterns = [
    path("", ProfileView.as_view(), name="detail"),
    path("change-username/", ChangeUsernameView.as_view(), name="change-username"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
]
