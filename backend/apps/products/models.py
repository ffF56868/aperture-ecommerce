"""Category & Product models."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from core.mixins import OrderableMixin, TimeStampedMixin


class Category(TimeStampedMixin, OrderableMixin):
    """A product category (e.g. 'Electronics', 'Home & Kitchen')."""

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ("ordering", "name")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(TimeStampedMixin, OrderableMixin):
    """A sellable product belonging to a category."""

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    short_description = models.CharField(max_length=300, blank=True)
    full_description = models.TextField(blank=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)

    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    delivery_estimate_days = models.PositiveSmallIntegerField(
        default=3, help_text="Estimated number of days for delivery/preparation."
    )

    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ("ordering", "-created_at")
        indexes = [
            models.Index(fields=["is_available", "is_featured"]),
            models.Index(fields=["category", "is_available"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def in_stock(self) -> bool:
        return self.is_available and self.stock_quantity > 0
