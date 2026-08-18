"""Shared abstract model mixins used across domain apps."""

import uuid

from django.db import models


class UUIDPrimaryKeyMixin(models.Model):
    """Adds a UUID primary key instead of the default auto-incrementing integer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedMixin(models.Model):
    """Adds self-updating `created_at` / `updated_at` timestamp fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-created_at",)


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted rows by default."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class SoftDeleteMixin(models.Model):
    """Adds a `deleted_at` flag and a manager that filters soft-deleted rows out."""

    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        from django.utils import timezone

        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])


class OrderableMixin(models.Model):
    """Adds a manual `ordering` integer field for admin-controlled display order."""

    ordering = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ("ordering",)
