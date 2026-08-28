from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    fields = ("name", "slug", "description", "image", "is_active")
    ordering = ("ordering", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price",
        "stock_quantity",
        "is_available",
        "is_featured",
        "ordering",
    )
    list_filter = ("is_available", "is_featured", "category")
    search_fields = ("name", "slug", "short_description")
    autocomplete_fields = ("category",)
    fieldsets = (
        ("基本信息", {"fields": ("category", "name", "slug", "short_description", "full_description", "image")} ),
        ("销售设置", {"fields": ("price", "stock_quantity", "delivery_estimate_days", "is_available", "is_featured")} ),
    )
    ordering = ("ordering", "-created_at")
