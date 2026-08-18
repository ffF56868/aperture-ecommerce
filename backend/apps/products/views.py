"""Public read-only viewsets for categories and products."""

from django.db.models import Count
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from core.pagination import StandardResultsSetPagination

from .filters import ProductFilter
from .models import Category, Product
from .serializers import CategorySerializer, ProductDetailSerializer, ProductListSerializer


@extend_schema_view(
    list=extend_schema(summary="List active categories", tags=["Categories"]),
    retrieve=extend_schema(summary="Retrieve a category by slug", tags=["Categories"]),
)
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Public read-only access to product categories."""

    queryset = Category.objects.filter(is_active=True).annotate(_product_count=Count("products"))
    serializer_class = CategorySerializer
    permission_classes = (AllowAny,)
    lookup_field = "slug"
    pagination_class = None


@extend_schema_view(
    list=extend_schema(
        summary="List available products",
        tags=["Products"],
        parameters=[
            OpenApiParameter("category", str, description="Filter by category slug"),
            OpenApiParameter("popular", bool, description="Filter to featured/popular products"),
            OpenApiParameter("ordering", str, description="e.g. price, -price, created_at"),
        ],
    ),
    retrieve=extend_schema(summary="Retrieve a product by slug", tags=["Products"]),
)
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Public read-only access to products, with filtering/search/ordering/pagination."""

    queryset = Product.objects.filter(is_available=True).select_related("category")
    permission_classes = (AllowAny,)
    pagination_class = StandardResultsSetPagination
    lookup_field = "slug"
    filterset_class = ProductFilter
    search_fields = ("name", "short_description", "full_description")
    ordering_fields = ("price", "created_at", "ordering", "name")
    ordering = ("ordering", "-created_at")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer
