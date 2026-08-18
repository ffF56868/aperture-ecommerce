"""Routes: /api/v1/categories/, /api/v1/products/ (router mounted at root prefix)."""

from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ProductViewSet

app_name = "products"

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")

urlpatterns = router.urls
