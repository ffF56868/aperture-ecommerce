from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.after_sales.management.commands.seed_after_sales_demo import (
    DEMO_PASSWORD,
    DEMO_USERNAME,
)
from apps.authentication.models import User
from apps.cart_orders.models import Order
from apps.products.models import Category, Product


class SeedAfterSalesDemoCommandTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="售后测试分类")
        self.products = [
            Product.objects.create(
                category=category,
                name=f"售后测试商品 {index}",
                price="99.00",
                stock_quantity=50,
            )
            for index in range(1, 5)
        ]

    def test_command_creates_four_idempotent_order_scenarios_without_changing_stock(self):
        stock_before = {product.id: product.stock_quantity for product in self.products}

        call_command("seed_after_sales_demo", stdout=StringIO())
        call_command("seed_after_sales_demo", stdout=StringIO())

        user = User.objects.get(username=DEMO_USERNAME)
        self.assertTrue(user.check_password(DEMO_PASSWORD))
        self.assertEqual(user.orders.count(), 4)
        self.assertSetEqual(
            set(user.orders.values_list("status", flat=True)),
            {Order.Status.PENDING, Order.Status.PAID, Order.Status.SHIPPED, Order.Status.CANCELLED},
        )

        for product in self.products:
            product.refresh_from_db()
            self.assertEqual(product.stock_quantity, stock_before[product.id])
