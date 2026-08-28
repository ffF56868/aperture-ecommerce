from django.contrib import admin

from .models import Cart, CartItem, Order, OrderItem, Payment


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ("product",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "total_items", "subtotal", "updated_at")
    search_fields = ("user__username",)
    inlines = (CartItemInline,)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "unit_price", "quantity")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_amount", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "user__username")
    readonly_fields = (
        "id",
        "subtotal",
        "tax_amount",
        "shipping_amount",
        "total_amount",
        "created_at",
    )
    inlines = (OrderItemInline,)
    actions = ("mark_as_shipped",)

    @admin.action(description="将所选已支付订单标记为已发货")
    def mark_as_shipped(self, request, queryset):
        updated = queryset.filter(status=Order.Status.PAID).update(status=Order.Status.SHIPPED)
        if updated:
            self.message_user(request, f"已将 {updated} 笔订单标记为已发货。")
        else:
            self.message_user(request, "没有可发货的已支付订单。", level="warning")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "order", "amount", "status", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("transaction_id", "order__id")
