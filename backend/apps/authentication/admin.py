from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import OTPVerification, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ("-created_at",)
    list_display = (
        "username",
        "phone_number",
        "email",
        "is_phone_verified",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_phone_verified", "is_staff", "is_active")
    search_fields = ("username", "phone_number", "email")
    readonly_fields = ("created_at", "updated_at", "last_login")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("phone_number", "email")}),
        ("Verification", {"fields": ("is_phone_verified",)}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "phone_number",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "purpose", "is_verified", "attempt_count", "created_at")
    list_filter = ("purpose", "is_verified")
    search_fields = ("phone_number",)
    readonly_fields = ("created_at", "updated_at")
