from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.after_sales.models import (
    AfterSalesCase,
    AgentConversation,
    ConfirmationRequest,
    CustomerMemory,
)
from apps.authentication.models import User


class AfterSalesModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="after_sales_model_user",
            phone_number="+8613800138001",
            password="Demo123!",
        )

    def test_after_sales_case_generates_a_customer_reference(self):
        case = AfterSalesCase.objects.create(
            user=self.user,
            case_type=AfterSalesCase.CaseType.HUMAN_SERVICE,
            reason="需要人工协助。",
        )

        self.assertTrue(case.case_number.startswith("AS-"))
        self.assertEqual(case.status, AfterSalesCase.Status.PENDING_REVIEW)
        self.assertEqual(case.priority, AfterSalesCase.Priority.NORMAL)

    def test_pending_confirmation_reports_expiry(self):
        conversation = AgentConversation.objects.create(user=self.user)
        confirmation = ConfirmationRequest.objects.create(
            conversation=conversation,
            user=self.user,
            action_type=ConfirmationRequest.ActionType.REFUND_REQUEST,
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertTrue(confirmation.is_expired)

    def test_customer_memory_is_unique_per_user_type_and_key(self):
        CustomerMemory.objects.create(
            user=self.user,
            memory_type=CustomerMemory.MemoryType.PREFERENCE,
            key="language",
            value={"value": "zh-CN"},
        )

        with self.assertRaises(IntegrityError):
            CustomerMemory.objects.create(
                user=self.user,
                memory_type=CustomerMemory.MemoryType.PREFERENCE,
                key="language",
                value={"value": "zh-CN"},
            )
