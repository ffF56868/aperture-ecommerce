"""Serializers for the products app."""

from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True, source="products.count")

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "image",
            "ordering",
            "is_active",
            "product_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "slug", "created_at", "updated_at")


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list/grid views."""

    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "category",
            "category_name",
            "short_description",
            "image",
            "price",
            "in_stock",
            "is_featured",
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    """Full serializer for the product detail page."""

    category = CategorySerializer(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "category",
            "name",
            "slug",
            "short_description",
            "full_description",
            "image",
            "price",
            "stock_quantity",
            "delivery_estimate_days",
            "is_available",
            "is_featured",
            "in_stock",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "slug", "created_at", "updated_at")
