from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.after_sales.models import AfterSalesCase, AgentConversation, ConfirmationRequest, ToolExecution
from apps.after_sales.workflow import prepare_confirmation
from apps.authentication.models import User
from apps.cart_orders.models import Order, OrderItem
from apps.products.models import Category, Product


class ConfirmationWorkflowAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="confirmation_owner",
            phone_number="+8613800138011",
            password="Demo123!",
        )
        self.other_user = User.objects.create_user(
            username="confirmation_other",
            phone_number="+8613800138012",
            password="Demo123!",
        )
        self.conversation = AgentConversation.objects.create(user=self.user)
        category = Category.objects.create(name="售后测试分类")
        self.product = Product.objects.create(
            category=category,
            name="售后测试短袖",
            price=Decimal("59.90"),
            stock_quantity=3,
        )
        self.client.force_authenticate(self.user)

    def _create_order(self, status):
        order = Order.objects.create(
            user=self.user,
            status=status,
            subtotal=Decimal("59.90"),
            total_amount=Decimal("59.90"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("59.90"),
            quantity=2,
        )
        return order

    def _prepare(self, order, policy_key, reason="尺码不合适"):
        confirmation, _ = prepare_confirmation(
            user=self.user,
            conversation=self.conversation,
            order_id=order.id,
            policy_key=policy_key,
            reason=reason,
        )
        return confirmation

    def test_refund_stays_pending_until_confirmed_and_repeated_click_is_idempotent(self):
        order = self._create_order(Order.Status.PAID)
        confirmation = self._prepare(order, "refund")

        first_response = self.client.post(
            f"/api/v1/after-sales/confirmations/{confirmation.id}/confirm/"
        )
        second_response = self.client.post(
            f"/api/v1/after-sales/confirmations/{confirmation.id}/confirm/"
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertFalse(first_response.data["already_executed"])
        self.assertTrue(second_response.data["already_executed"])
        self.assertEqual(AfterSalesCase.objects.count(), 1)
        after_sales_case = AfterSalesCase.objects.get()
        self.assertEqual(after_sales_case.case_type, AfterSalesCase.CaseType.REFUND)
        self.assertEqual(after_sales_case.status, AfterSalesCase.Status.PENDING_REVIEW)
        confirmation.refresh_from_db()
        self.assertEqual(confirmation.status, ConfirmationRequest.Status.EXECUTED)
        self.assertEqual(
            ToolExecution.objects.filter(
                confirmation_request=confirmation,
                initiated_by=ToolExecution.Initiator.HUMAN,
                status=ToolExecution.Status.SUCCEEDED,
            ).count(),
            1,
        )

    def test_pending_order_cancellation_restores_stock_after_explicit_confirmation(self):
        order = self._create_order(Order.Status.PENDING)
        confirmation = self._prepare(order, "cancel-order", "暂时不需要了")

        response = self.client.post(f"/api/v1/after-sales/confirmations/{confirmation.id}/confirm/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["after_sales_case"])
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertEqual(AfterSalesCase.objects.count(), 0)

    def test_other_user_cannot_confirm_someone_elses_request(self):
        order = self._create_order(Order.Status.PAID)
        confirmation = self._prepare(order, "refund")
        self.client.force_authenticate(self.other_user)

        response = self.client.post(f"/api/v1/after-sales/confirmations/{confirmation.id}/confirm/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(AfterSalesCase.objects.count(), 0)

    def test_rejection_changes_no_order_or_case(self):
        order = self._create_order(Order.Status.PAID)
        confirmation = self._prepare(order, "refund")

        response = self.client.post(f"/api/v1/after-sales/confirmations/{confirmation.id}/reject/")

        self.assertEqual(response.status_code, 200)
        confirmation.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(confirmation.status, ConfirmationRequest.Status.REJECTED)
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(AfterSalesCase.objects.count(), 0)

    def test_expired_confirmation_cannot_be_executed(self):
        order = self._create_order(Order.Status.PAID)
        confirmation = self._prepare(order, "refund")
        confirmation.expires_at = timezone.now() - timedelta(seconds=1)
        confirmation.save(update_fields=["expires_at"])

        response = self.client.post(f"/api/v1/after-sales/confirmations/{confirmation.id}/confirm/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "CONFIRMATION_EXPIRED")
        confirmation.refresh_from_db()
        self.assertEqual(confirmation.status, ConfirmationRequest.Status.EXPIRED)
        self.assertEqual(AfterSalesCase.objects.count(), 0)

    @patch("apps.after_sales.workflow.AfterSalesCase.objects.create")
    def test_unexpected_ticket_failure_rolls_back_and_is_audited(self, mock_create):
        order = self._create_order(Order.Status.PAID)
        confirmation = self._prepare(order, "refund")
        mock_create.side_effect = RuntimeError("database write failed")

        response = self.client.post(f"/api/v1/after-sales/confirmations/{confirmation.id}/confirm/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "CONFIRMATION_EXECUTION_FAILED")
        confirmation.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(confirmation.status, ConfirmationRequest.Status.FAILED)
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(AfterSalesCase.objects.count(), 0)
        execution = ToolExecution.objects.get(confirmation_request=confirmation)
        self.assertEqual(execution.status, ToolExecution.Status.FAILED)
        self.assertEqual(execution.error_code, "CONFIRMATION_EXECUTION_FAILED")
