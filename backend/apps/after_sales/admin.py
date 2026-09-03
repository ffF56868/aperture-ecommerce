from django.contrib import admin

from .models import (
    AfterSalesCase,
    AgentConversation,
    AgentMessage,
    AfterSalesNotification,
    ConfirmationRequest,
    CustomerMemory,
    KnowledgeChunk,
    KnowledgeDocument,
    ToolExecution,
)


class AgentMessageInline(admin.TabularInline):
    model = AgentMessage
    extra = 0
    can_delete = False
    fields = ("role", "content", "tool_name", "created_at")
    readonly_fields = fields
    ordering = ("created_at",)


class ToolExecutionInline(admin.TabularInline):
    model = ToolExecution
    extra = 0
    can_delete = False
    fields = (
        "agent_role",
        "tool_name",
        "action_kind",
        "status",
        "error_code",
        "duration_ms",
        "created_at",
    )
    readonly_fields = fields
    ordering = ("-created_at",)


class KnowledgeChunkInline(admin.TabularInline):
    model = KnowledgeChunk
    extra = 0
    can_delete = False
    fields = ("sequence", "content", "content_hash", "created_at")
    readonly_fields = fields
    ordering = ("sequence",)


@admin.register(AfterSalesCase)
class AfterSalesCaseAdmin(admin.ModelAdmin):
    list_display = (
        "case_number",
        "case_type",
        "status",
        "priority",
        "user",
        "order",
        "assigned_to",
        "created_at",
    )
    list_filter = ("case_type", "status", "priority")
    search_fields = ("case_number", "user__username", "order__id", "reason")
    autocomplete_fields = ("user", "order", "conversation", "confirmation_request", "assigned_to")
    readonly_fields = ("id", "case_number", "created_at", "updated_at")
    fieldsets = (
        ("工单信息", {"fields": ("id", "case_number", "case_type", "status", "priority")} ),
        ("关联对象", {"fields": ("user", "order", "conversation", "confirmation_request")} ),
        ("处理内容", {"fields": ("reason", "agent_summary", "staff_note", "assigned_to", "resolved_at")} ),
        ("时间", {"fields": ("created_at", "updated_at")} ),
    )
    inlines = (ToolExecutionInline,)


@admin.register(AgentConversation)
class AgentConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "state", "current_intent", "selected_order", "last_active_at")
    list_filter = ("state", "current_intent")
    search_fields = ("id", "user__username", "summary")
    autocomplete_fields = ("user", "selected_order")
    readonly_fields = ("id", "created_at", "updated_at", "last_active_at")
    inlines = (AgentMessageInline, ToolExecutionInline)


@admin.register(ConfirmationRequest)
class ConfirmationRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "action_type", "status", "user", "order", "expires_at", "created_at")
    list_filter = ("action_type", "status")
    search_fields = ("id", "user__username", "order__id")
    autocomplete_fields = ("conversation", "user", "order")
    readonly_fields = (
        "id",
        "idempotency_key",
        "payload",
        "result",
        "created_at",
        "updated_at",
        "confirmed_at",
        "executed_at",
    )


@admin.register(CustomerMemory)
class CustomerMemoryAdmin(admin.ModelAdmin):
    list_display = ("user", "memory_type", "key", "is_active", "updated_at")
    list_filter = ("memory_type", "is_active")
    search_fields = ("user__username", "key")
    autocomplete_fields = ("user", "source_conversation")
    readonly_fields = ("created_at", "updated_at")


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "source_label", "is_published", "updated_at")
    list_filter = ("category", "is_published")
    search_fields = ("title", "source_label", "content")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (KnowledgeChunkInline,)


@admin.register(ToolExecution)
class ToolExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "agent_role",
        "tool_name",
        "action_kind",
        "status",
        "initiated_by",
        "user",
        "duration_ms",
        "created_at",
    )
    list_filter = ("action_kind", "status", "initiated_by", "tool_name")
    search_fields = ("tool_name", "user__username", "error_code")
    autocomplete_fields = ("conversation", "user", "after_sales_case", "confirmation_request")
    readonly_fields = (
        "id",
        "conversation",
        "user",
        "after_sales_case",
        "confirmation_request",
        "agent_role",
        "tool_name",
        "action_kind",
        "status",
        "initiated_by",
        "sanitized_arguments",
        "result",
        "error_code",
        "duration_ms",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AfterSalesNotification)
class AfterSalesNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "event_type",
        "user",
        "after_sales_case",
        "is_read",
        "email_status",
        "created_at",
    )
    list_filter = ("event_type", "is_read", "email_status")
    search_fields = ("title", "message", "user__username", "after_sales_case__case_number")
    autocomplete_fields = ("user", "after_sales_case")
    readonly_fields = (
        "id",
        "user",
        "after_sales_case",
        "event_type",
        "title",
        "message",
        "action_url",
        "is_read",
        "read_at",
        "email_status",
        "email_sent_at",
        "email_error",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
