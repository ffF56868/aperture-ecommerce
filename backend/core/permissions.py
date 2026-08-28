"""Shared DRF permission classes used across apps."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwner(BasePermission):
    """Object-level permission: only the owning user may access the object."""

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None)
        return owner is not None and owner == request.user


class IsVerifiedUser(BasePermission):
    """Grants access only to authenticated users with a phone-verified account."""

    message = "完成手机号验证后才能执行此操作。"

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "is_phone_verified", False)
        )


class ReadOnlyOrIsAdmin(BasePermission):
    """Allow safe (read) methods to anyone; writes are restricted to staff/admin users."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)
