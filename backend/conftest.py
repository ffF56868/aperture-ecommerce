"""Shared pytest fixtures."""

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def category(db):
    from apps.products.models import Category

    return Category.objects.create(name="Electronics")


@pytest.fixture
def product(db, category):
    from apps.products.models import Product

    return Product.objects.create(
        category=category,
        name="Wireless Mouse",
        price="29.99",
        stock_quantity=10,
    )


@pytest.fixture
def verified_user(db):
    from apps.authentication.models import User

    user = User.objects.create_user(
        username="buyer1", phone_number="+14155552671", password="S3curePass!"
    )
    user.is_phone_verified = True
    user.save(update_fields=["is_phone_verified"])
    return user


@pytest.fixture
def auth_client(api_client, verified_user):
    api_client.force_authenticate(user=verified_user)
    return api_client
