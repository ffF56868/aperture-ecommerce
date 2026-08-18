import pytest

pytestmark = pytest.mark.django_db


class TestCart:
    def test_add_item_creates_cart(self, auth_client, product):
        response = auth_client.post(
            "/api/v1/cart/add/", {"product_id": str(product.id), "quantity": 2}, format="json"
        )
        assert response.status_code == 201
        assert response.data["total_items"] == 2
        assert float(response.data["subtotal"]) == float(product.price) * 2

    def test_add_same_item_twice_increments_quantity(self, auth_client, product):
        auth_client.post(
            "/api/v1/cart/add/", {"product_id": str(product.id), "quantity": 1}, format="json"
        )
        response = auth_client.post(
            "/api/v1/cart/add/", {"product_id": str(product.id), "quantity": 1}, format="json"
        )
        assert response.status_code == 201
        assert response.data["items"][0]["quantity"] == 2

    def test_cart_requires_authentication(self, api_client, product):
        response = api_client.post(
            "/api/v1/cart/add/", {"product_id": str(product.id), "quantity": 1}, format="json"
        )
        assert response.status_code == 401

    def test_clear_cart(self, auth_client, product):
        auth_client.post(
            "/api/v1/cart/add/", {"product_id": str(product.id), "quantity": 1}, format="json"
        )
        response = auth_client.delete("/api/v1/cart/clear/")
        assert response.status_code == 200
        assert response.data["total_items"] == 0


class TestCheckout:
    def test_checkout_creates_order_and_decrements_stock(self, auth_client, product):
        auth_client.post(
            "/api/v1/cart/add/", {"product_id": str(product.id), "quantity": 3}, format="json"
        )
        response = auth_client.post(
            "/api/v1/orders/checkout/", {"shipping_address": "123 Main St"}, format="json"
        )
        assert response.status_code == 201
        assert response.data["status"] == "PENDING"
        assert len(response.data["items"]) == 1

        product.refresh_from_db()
        assert product.stock_quantity == 7

    def test_checkout_fails_with_empty_cart(self, auth_client):
        response = auth_client.post(
            "/api/v1/orders/checkout/", {"shipping_address": "123 Main St"}, format="json"
        )
        assert response.status_code == 400

    def test_checkout_fails_when_stock_insufficient(self, auth_client, product):
        auth_client.post(
            "/api/v1/cart/add/", {"product_id": str(product.id), "quantity": 999}, format="json"
        )
        response = auth_client.post(
            "/api/v1/orders/checkout/", {"shipping_address": "123 Main St"}, format="json"
        )
        assert response.status_code == 400


class TestPayments:
    def test_initiate_then_verify_marks_order_paid(self, auth_client, product):
        auth_client.post(
            "/api/v1/cart/add/", {"product_id": str(product.id), "quantity": 1}, format="json"
        )
        order = auth_client.post(
            "/api/v1/orders/checkout/", {"shipping_address": "123 Main St"}, format="json"
        ).data

        initiate = auth_client.post(
            "/api/v1/payments/initiate/", {"order_id": order["id"]}, format="json"
        )
        assert initiate.status_code == 201

        verify = auth_client.post(
            "/api/v1/payments/verify/",
            {"transaction_id": initiate.data["transaction_id"], "success": True},
            format="json",
        )
        assert verify.status_code == 200
        assert verify.data["order_status"] == "PAID"
