"""Routes: /api/v1/cart/..., /api/v1/orders/..., /api/v1/payments/..."""

from django.urls import path

from .views import (
    CartAddView,
    CartClearView,
    CartDetailView,
    CartItemRemoveView,
    CartItemUpdateView,
    CheckoutView,
    InitiatePaymentView,
    OrderCancelView,
    OrderListView,
    VerifyPaymentView,
)

app_name = "cart_orders"

urlpatterns = [
    # Cart
    path("cart/", CartDetailView.as_view(), name="cart-detail"),
    path("cart/add/", CartAddView.as_view(), name="cart-add"),
    path("cart/items/<int:item_id>/", CartItemUpdateView.as_view(), name="cart-item-update"),
    path("cart/items/<int:item_id>/remove/", CartItemRemoveView.as_view(), name="cart-item-remove"),
    path("cart/clear/", CartClearView.as_view(), name="cart-clear"),
    # Orders
    path("orders/", OrderListView.as_view(), name="order-list"),
    path("orders/checkout/", CheckoutView.as_view(), name="order-checkout"),
    path("orders/<uuid:order_id>/cancel/", OrderCancelView.as_view(), name="order-cancel"),
    # Payments
    path("payments/initiate/", InitiatePaymentView.as_view(), name="payment-initiate"),
    path("payments/verify/", VerifyPaymentView.as_view(), name="payment-verify"),
]
