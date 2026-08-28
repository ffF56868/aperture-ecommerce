"""Routes for the after-sales Agent domain."""

from django.urls import path

from .views import (
    AfterSalesPolicyDetailView,
    AfterSalesPolicyListView,
    AgentConversationDetailView,
    AgentConversationMessageView,
)


app_name = "after_sales"

urlpatterns = [
    path("policies/", AfterSalesPolicyListView.as_view(), name="policy-list"),
    path("policies/<str:policy_key>/", AfterSalesPolicyDetailView.as_view(), name="policy-detail"),
    path("conversations/", AgentConversationMessageView.as_view(), name="conversation-message"),
    path(
        "conversations/<uuid:conversation_id>/",
        AgentConversationDetailView.as_view(),
        name="conversation-detail",
    ),
]
