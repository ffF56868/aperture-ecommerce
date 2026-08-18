"""Views for cart management, checkout, and payment initiation/verification."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Cart, CartItem, Order
from .serializers import (
    AddToCartSerializer,
    CartSerializer,
    CheckoutSerializer,
    InitiatePaymentSerializer,
    OrderSerializer,
    UpdateCartItemSerializer,
    VerifyPaymentSerializer,
)


class CartMixin:
    permission_classes = (IsAuthenticated,)

    def get_cart(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart


@extend_schema(summary="Retrieve the authenticated user's cart", tags=["Cart"])
class CartDetailView(CartMixin, generics.RetrieveAPIView):
    serializer_class = CartSerializer

    def get_object(self):
        return self.get_cart()


@extend_schema(summary="Add a product to the cart (or increase its quantity)", tags=["Cart"])
class CartAddView(CartMixin, generics.GenericAPIView):
    serializer_class = AddToCartSerializer

    def post(self, request, *args, **kwargs):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = self.get_cart()
        product = serializer.validated_data["product_id"]
        quantity = serializer.validated_data["quantity"]

        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={"quantity": quantity}
        )
        if not created:
            item.quantity += quantity
            item.save(update_fields=["quantity"])

        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


@extend_schema(summary="Update a cart item's quantity", tags=["Cart"])
class CartItemUpdateView(CartMixin, generics.GenericAPIView):
    serializer_class = UpdateCartItemSerializer

    def patch(self, request, item_id, *args, **kwargs):
        cart = self.get_cart()
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item.quantity = serializer.validated_data["quantity"]
        item.save(update_fields=["quantity"])
        return Response(CartSerializer(cart).data)


@extend_schema(summary="Remove a single item from the cart", tags=["Cart"])
class CartItemRemoveView(CartMixin, generics.GenericAPIView):
    serializer_class = CartSerializer

    def delete(self, request, item_id, *args, **kwargs):
        cart = self.get_cart()
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()
        return Response(CartSerializer(cart).data)


@extend_schema(summary="Clear all items from the cart", tags=["Cart"])
class CartClearView(CartMixin, generics.GenericAPIView):
    serializer_class = CartSerializer

    def delete(self, request, *args, **kwargs):
        cart = self.get_cart()
        cart.items.all().delete()
        return Response(CartSerializer(cart).data)


@extend_schema(summary="Checkout — create an order from the current cart", tags=["Orders"])
class CheckoutView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = CheckoutSerializer

    def post(self, request, *args, **kwargs):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(
            data=request.data, context={"cart": cart, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


@extend_schema(summary="List the authenticated user's order history", tags=["Orders"])
class OrderListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderSerializer
    queryset = Order.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return Order.objects.filter(user=self.request.user).prefetch_related("items")


@extend_schema(summary="Initiate a payment for a pending order", tags=["Payments"])
class InitiatePaymentView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = InitiatePaymentSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(
            {
                "transaction_id": payment.transaction_id,
                "amount": str(payment.amount),
                "status": payment.status,
                "redirect_url": f"/mock-gateway/pay/{payment.transaction_id}/",
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    summary="Verify a payment (webhook/callback endpoint from the payment gateway)",
    tags=["Payments"],
)
class VerifyPaymentView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = VerifyPaymentSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(
            {
                "transaction_id": payment.transaction_id,
                "status": payment.status,
                "order_status": payment.order.status,
            }
        )
