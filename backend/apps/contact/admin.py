from django.contrib import admin

from .models import ContactInquiry


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "subject", "is_resolved", "created_at")
    list_filter = ("is_resolved",)
    search_fields = ("full_name", "email", "subject", "message")
    readonly_fields = ("created_at", "updated_at")
