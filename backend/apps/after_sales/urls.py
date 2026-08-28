"""Routes for the after-sales Agent domain."""

from django.urls import path

from .views import AfterSalesPolicyDetailView, AfterSalesPolicyListView


app_name = "after_sales"

urlpatterns = [
    path("policies/", AfterSalesPolicyListView.as_view(), name="policy-list"),
    path("policies/<str:policy_key>/", AfterSalesPolicyDetailView.as_view(), name="policy-detail"),
]
