from django.test import TestCase
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.cart_orders.models import Payment
from apps.products.models import Category, Product


class OrderStateActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="order_action_user",
            phone_number="+8613800138010",
            password="Demo123!",
        )
        category = Category.objects.create(name="订单状态测试分类")
        self.product = Product.objects.create(
            category=category,
            name="订单状态测试商品",
            price="99.00",
            stock_quantity=10,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create_pending_order(self, quantity=2):
        self.client.post(
            "/api/v1/cart/add/",
            {"product_id": str(self.product.id), "quantity": quantity},
            format="json",
        )
        return self.client.post(
            "/api/v1/orders/checkout/",
            {"shipping_address": "测试收货地址"},
            format="json",
        ).data

    def test_user_can_cancel_pending_order_and_stock_is_restored(self):
        order = self.create_pending_order()

        response = self.client.post(f"/api/v1/orders/{order['id']}/cancel/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "CANCELLED")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

    def test_paid_order_cannot_be_cancelled_directly(self):
        order = self.create_pending_order(quantity=1)
        payment = self.client.post(
            "/api/v1/payments/initiate/",
            {"order_id": order["id"]},
            format="json",
        ).data
        self.client.post(
            "/api/v1/payments/verify/",
            {"transaction_id": payment["transaction_id"], "success": True},
            format="json",
        )

        response = self.client.post(f"/api/v1/orders/{order['id']}/cancel/")

        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 9)

    def test_failed_payment_cancels_order_and_restores_stock(self):
        order = self.create_pending_order(quantity=3)
        payment = self.client.post(
            "/api/v1/payments/initiate/",
            {"order_id": order["id"]},
            format="json",
        ).data

        response = self.client.post(
            "/api/v1/payments/verify/",
            {"transaction_id": payment["transaction_id"], "success": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["order_status"], "CANCELLED")
        self.assertEqual(
            Payment.objects.get(transaction_id=payment["transaction_id"]).status,
            Payment.Status.FAILED,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
