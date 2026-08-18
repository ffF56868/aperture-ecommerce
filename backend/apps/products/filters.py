"""Filtering support for the product list endpoint."""

import django_filters

from .models import Product


class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category__slug", lookup_expr="exact")
    popular = django_filters.BooleanFilter(field_name="is_featured")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = Product
        fields = ("category", "popular", "min_price", "max_price", "in_stock")

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(is_available=True, stock_quantity__gt=0)
        return queryset
