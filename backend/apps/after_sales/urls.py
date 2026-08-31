"""Routes for the after-sales Agent domain."""

from django.urls import path

from .views import (
    AfterSalesCaseListView,
    AfterSalesPolicyDetailView,
    AfterSalesPolicyListView,
    AgentConversationDetailView,
    AgentConversationMessageView,
    ConfirmationExecuteView,
    ConfirmationRejectView,
    StaffAfterSalesCaseDetailView,
    StaffAfterSalesCaseListView,
    StaffAfterSalesCaseRefundOrderView,
    StaffAfterSalesCaseShipOrderView,
    StaffOrderListView,
    StaffOrderShipView,
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
    path("cases/", AfterSalesCaseListView.as_view(), name="case-list"),
    path("staff/cases/", StaffAfterSalesCaseListView.as_view(), name="staff-case-list"),
    path(
        "staff/cases/<uuid:case_id>/",
        StaffAfterSalesCaseDetailView.as_view(),
        name="staff-case-detail",
    ),
    path(
        "staff/cases/<uuid:case_id>/ship-order/",
        StaffAfterSalesCaseShipOrderView.as_view(),
        name="staff-case-ship-order",
    ),
    path(
        "staff/cases/<uuid:case_id>/refund-order/",
        StaffAfterSalesCaseRefundOrderView.as_view(),
        name="staff-case-refund-order",
    ),
    path("staff/orders/", StaffOrderListView.as_view(), name="staff-order-list"),
    path(
        "staff/orders/<uuid:order_id>/ship/",
        StaffOrderShipView.as_view(),
        name="staff-order-ship",
    ),
    path(
        "confirmations/<uuid:confirmation_id>/confirm/",
        ConfirmationExecuteView.as_view(),
        name="confirmation-execute",
    ),
    path(
        "confirmations/<uuid:confirmation_id>/reject/",
        ConfirmationRejectView.as_view(),
        name="confirmation-reject",
    ),
]
