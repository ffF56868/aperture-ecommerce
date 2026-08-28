"""Serializers for cart, checkout, and payment flows."""

from decimal import Decimal

from rest_framework import serializers

from apps.products.models import Product

from .models import Cart, CartItem, Order, OrderItem, Payment
from .services import OrderTransitionError, cancel_pending_order


class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        source="product", queryset=Product.objects.filter(is_available=True), write_only=True
    )
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_image = serializers.ImageField(source="product.image", read_only=True)
    unit_price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2, read_only=True
    )
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product_id",
            "product_name",
            "product_slug",
            "product_image",
            "unit_price",
            "quantity",
            "line_total",
        )
        read_only_fields = ("id",)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ("id", "items", "subtotal", "total_items", "updated_at")


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_available=True)
    )
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_name", "unit_price", "quantity", "line_total")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "subtotal",
            "tax_amount",
            "shipping_amount",
            "total_amount",
            "shipping_address",
            "items",
            "created_at",
        )
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    """Creates an Order (with item snapshots) from the user's current cart, then clears it."""

    shipping_address = serializers.CharField(allow_blank=True, required=False, default="")
    tax_rate = serializers.DecimalField(
        max_digits=4, decimal_places=3, required=False, default=Decimal("0.000")
    )
    shipping_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=Decimal("0.00")
    )

    def validate(self, attrs):
        cart: Cart = self.context["cart"]
        if not cart.items.exists():
            raise serializers.ValidationError("Your cart is empty.")
        for item in cart.items.select_related("product"):
            if not item.product.in_stock or item.product.stock_quantity < item.quantity:
                raise serializers.ValidationError(
                    f"'{item.product.name}' does not have enough stock."
                )
        return attrs

    def create(self, validated_data):
        from django.db import transaction

        cart: Cart = self.context["cart"]
        user = self.context["request"].user

        with transaction.atomic():
            subtotal = cart.subtotal
            tax_amount = (subtotal * validated_data["tax_rate"]).quantize(Decimal("0.01"))
            shipping_amount = validated_data["shipping_amount"]
            total_amount = subtotal + tax_amount + shipping_amount

            order = Order.objects.create(
                user=user,
                subtotal=subtotal,
                tax_amount=tax_amount,
                shipping_amount=shipping_amount,
                total_amount=total_amount,
                shipping_address=validated_data.get("shipping_address", ""),
            )

            for item in cart.items.select_related("product"):
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    unit_price=item.product.price,
                    quantity=item.quantity,
                )
                item.product.stock_quantity -= item.quantity
                item.product.save(update_fields=["stock_quantity"])

            cart.items.all().delete()

        return order


class InitiatePaymentSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()

    def validate_order_id(self, value):
        request = self.context["request"]
        try:
            order = Order.objects.get(id=value, user=request.user)
        except Order.DoesNotExist as exc:
            raise serializers.ValidationError("Order not found.") from exc
        if order.status != Order.Status.PENDING:
            raise serializers.ValidationError("This order is not payable.")
        self.context["order"] = order
        return value

    def create(self, validated_data):
        import uuid

        order = self.context["order"]
        payment, _ = Payment.objects.update_or_create(
            order=order,
            defaults={
                "transaction_id": f"txn_{uuid.uuid4().hex[:20]}",
                "amount": order.total_amount,
                "status": Payment.Status.INITIATED,
            },
        )
        return payment


class VerifyPaymentSerializer(serializers.Serializer):
    """Simulates the payment gateway's callback/webhook verification step."""

    transaction_id = serializers.CharField()
    success = serializers.BooleanField(default=True)

    def validate_transaction_id(self, value):
        try:
            payment = Payment.objects.select_related("order").get(transaction_id=value)
        except Payment.DoesNotExist as exc:
            raise serializers.ValidationError("Unknown transaction.") from exc
        self.context["payment"] = payment
        return value

    def save(self, **kwargs):
        payment: Payment = self.context["payment"]
        if self.validated_data["success"]:
            from django.db import transaction

            with transaction.atomic():
                payment = Payment.objects.select_for_update().select_related("order").get(id=payment.id)
                if payment.order.status != Order.Status.PENDING:
                    raise serializers.ValidationError("订单不处于待支付状态，无法完成支付。")
                payment.raw_callback_payload = self.validated_data
                payment.status = Payment.Status.SUCCESS
                payment.order.status = Order.Status.PAID
                payment.save(update_fields=["status", "raw_callback_payload"])
                payment.order.save(update_fields=["status"])
                return payment

        try:
            cancel_pending_order(
                payment.order_id,
                payment_callback_payload=self.validated_data,
            )
        except OrderTransitionError as exc:
            raise serializers.ValidationError(str(exc)) from exc

        payment.refresh_from_db()
        return payment
