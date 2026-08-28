"""Transactional order state transitions shared by APIs and payment callbacks."""

from django.db import transaction
from django.db.models import F

from apps.products.models import Product

from .models import Order, Payment


class OrderTransitionError(Exception):
    """Raised when an order cannot perform the requested state transition."""


@transaction.atomic
def cancel_pending_order(order_id, *, user=None, payment_callback_payload=None):
    """Cancel one pending order and return its reserved stock exactly once."""

    orders = Order.objects.select_for_update().prefetch_related("items")
    if user is not None:
        orders = orders.filter(user=user)
    order = orders.get(id=order_id)

    if order.status != Order.Status.PENDING:
        raise OrderTransitionError("只有待支付订单可以取消。")

    for item in order.items.all():
        if item.product_id is None:
            continue
        Product.objects.select_for_update().filter(id=item.product_id).update(
            stock_quantity=F("stock_quantity") + item.quantity
        )

    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status"])

    payment = Payment.objects.select_for_update().filter(order=order).first()
    if payment is not None:
        payment.status = Payment.Status.FAILED
        update_fields = ["status"]
        if payment_callback_payload is not None:
            payment.raw_callback_payload = payment_callback_payload
            update_fields.append("raw_callback_payload")
        payment.save(update_fields=update_fields)

    return order
