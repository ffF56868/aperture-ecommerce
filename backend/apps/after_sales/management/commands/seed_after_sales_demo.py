"""Create repeatable user and order data for after-sales Agent demonstrations."""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.cart_orders.models import Order, OrderItem, Payment
from apps.products.models import Product


DEMO_USERNAME = "售后测试用户"
DEMO_PHONE_NUMBER = "+8613800138000"
DEMO_PASSWORD = "Demo123!"
DEMO_ADDRESS_PREFIX = "[售后 Agent 演示数据]"

DEMO_ORDERS = (
    {
        "key": "pending",
        "label": "待支付取消订单",
        "status": Order.Status.PENDING,
        "payment_status": None,
    },
    {
        "key": "paid",
        "label": "已支付退款订单",
        "status": Order.Status.PAID,
        "payment_status": Payment.Status.SUCCESS,
    },
    {
        "key": "shipped",
        "label": "已发货退货订单",
        "status": Order.Status.SHIPPED,
        "payment_status": Payment.Status.SUCCESS,
    },
    {
        "key": "cancelled",
        "label": "已取消订单",
        "status": Order.Status.CANCELLED,
        "payment_status": Payment.Status.FAILED,
    },
)


def demo_order_id(key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"aperture-after-sales-demo:{key}")


class Command(BaseCommand):
    help = "创建或重置售后 Agent 的测试用户和四种订单状态演示数据。"

    def handle(self, *args, **options):
        products = list(Product.objects.filter(is_available=True).order_by("created_at")[:4])
        if len(products) < 4:
            raise CommandError("至少需要 4 个可销售商品，才能创建售后 Agent 演示订单。")

        user_model = get_user_model()
        with transaction.atomic():
            user, _ = user_model.objects.update_or_create(
                username=DEMO_USERNAME,
                defaults={
                    "phone_number": DEMO_PHONE_NUMBER,
                    "is_phone_verified": True,
                    "is_active": True,
                    "is_staff": False,
                },
            )
            user.set_password(DEMO_PASSWORD)
            user.save()

            seeded_orders = []
            for product, scenario in zip(products, DEMO_ORDERS, strict=True):
                order_id = demo_order_id(scenario["key"])
                price = product.price
                order, _ = Order.objects.update_or_create(
                    id=order_id,
                    defaults={
                        "user": user,
                        "status": scenario["status"],
                        "subtotal": price,
                        "tax_amount": Decimal("0.00"),
                        "shipping_amount": Decimal("0.00"),
                        "total_amount": price,
                        "shipping_address": f"{DEMO_ADDRESS_PREFIX} {scenario['label']}",
                    },
                )
                OrderItem.objects.filter(order=order).delete()
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    unit_price=price,
                    quantity=1,
                )

                if scenario["payment_status"] is None:
                    Payment.objects.filter(order=order).delete()
                else:
                    Payment.objects.update_or_create(
                        order=order,
                        defaults={
                            "provider": "mock_gateway",
                            "transaction_id": f"after_sales_demo_{scenario['key']}",
                            "amount": price,
                            "status": scenario["payment_status"],
                            "raw_callback_payload": {
                                "demo": True,
                                "scenario": scenario["key"],
                                "success": scenario["payment_status"] == Payment.Status.SUCCESS,
                            },
                        },
                    )
                seeded_orders.append((scenario["label"], order))

        self.stdout.write(self.style.SUCCESS("售后 Agent 演示数据已就绪。"))
        self.stdout.write(f"测试账号：{DEMO_USERNAME}")
        self.stdout.write(f"测试密码：{DEMO_PASSWORD}")
        for label, order in seeded_orders:
            self.stdout.write(f"{label}：{order.id}")
