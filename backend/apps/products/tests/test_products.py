import pytest

pytestmark = pytest.mark.django_db


class TestProductList:
    def test_list_only_returns_available_products(self, api_client, category):
        from apps.products.models import Product

        Product.objects.create(
            category=category, name="Available", price="10.00", is_available=True
        )
        Product.objects.create(category=category, name="Hidden", price="10.00", is_available=False)

        response = api_client.get("/api/v1/products/")
        assert response.status_code == 200
        names = [p["name"] for p in response.data["results"]]
        assert "Available" in names
        assert "Hidden" not in names

    def test_filter_by_category_slug(self, api_client, category, product):
        from apps.products.models import Category
        from apps.products.models import Product as ProductModel

        other_category = Category.objects.create(name="Books")
        ProductModel.objects.create(category=other_category, name="A Novel", price="15.00")

        response = api_client.get(f"/api/v1/products/?category={category.slug}")
        assert response.status_code == 200
        names = [p["name"] for p in response.data["results"]]
        assert product.name in names
        assert "A Novel" not in names

    def test_search_by_name(self, api_client, product):
        response = api_client.get("/api/v1/products/?search=Mouse")
        assert response.status_code == 200
        assert response.data["count"] == 1


class TestProductDetail:
    def test_retrieve_by_slug(self, api_client, product):
        response = api_client.get(f"/api/v1/products/{product.slug}/")
        assert response.status_code == 200
        assert response.data["name"] == product.name
        assert response.data["category"]["name"] == product.category.name

    def test_unknown_slug_returns_404(self, api_client):
        response = api_client.get("/api/v1/products/does-not-exist/")
        assert response.status_code == 404


class TestCategoryList:
    def test_list_active_categories(self, api_client, category):
        response = api_client.get("/api/v1/categories/")
        assert response.status_code == 200
        assert any(c["slug"] == category.slug for c in response.data)
