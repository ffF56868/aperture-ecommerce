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


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "order", "amount", "status", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("transaction_id", "order__id")
