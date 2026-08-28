"""Category & Product models."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from core.mixins import OrderableMixin, TimeStampedMixin


class Category(TimeStampedMixin, OrderableMixin):
    """A product category (e.g. 'Electronics', 'Home & Kitchen')."""

    name = models.CharField("分类名称", max_length=150, unique=True)
    slug = models.SlugField(
        "URL 标识",
        max_length=170,
        unique=True,
        blank=True,
        allow_unicode=True,
        help_text="可留空，系统会根据分类名称自动生成。",
    )
    description = models.TextField("分类描述", blank=True)
    image = models.ImageField("分类图片", upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "商品分类"
        verbose_name_plural = "商品分类"
        ordering = ("ordering", "name")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class Product(TimeStampedMixin, OrderableMixin):
    """A sellable product belonging to a category."""

    category = models.ForeignKey(
        Category, verbose_name="所属分类", on_delete=models.PROTECT, related_name="products"
    )
    name = models.CharField("商品名称", max_length=200)
    slug = models.SlugField(
        "URL 标识",
        max_length=220,
        unique=True,
        blank=True,
        allow_unicode=True,
        help_text="可留空，系统会根据商品名称自动生成。",
    )
    short_description = models.CharField("商品简述", max_length=300, blank=True)
    full_description = models.TextField("商品详情", blank=True)
    image = models.ImageField("商品图片", upload_to="products/", blank=True, null=True)

    price = models.DecimalField(
        "价格", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    stock_quantity = models.PositiveIntegerField("库存数量", default=0)
    delivery_estimate_days = models.PositiveSmallIntegerField(
        "预计送达天数", default=3, help_text="预计配送或备货所需的天数。"
    )

    is_available = models.BooleanField("可销售", default=True)
    is_featured = models.BooleanField("推荐商品", default=False)

    class Meta:
        verbose_name = "商品"
        verbose_name_plural = "商品"
        ordering = ("ordering", "-created_at")
        indexes = [
            models.Index(fields=["is_available", "is_featured"]),
            models.Index(fields=["category", "is_available"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    @property
    def in_stock(self) -> bool:
        return self.is_available and self.stock_quantity > 0
