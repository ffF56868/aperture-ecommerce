from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.after_sales.models import (
    AfterSalesCase,
    AgentConversation,
    ConfirmationRequest,
    CustomerMemory,
)


@pytest.mark.django_db
def test_after_sales_case_generates_a_customer_reference(verified_user):
    case = AfterSalesCase.objects.create(
        user=verified_user,
        case_type=AfterSalesCase.CaseType.HUMAN_SERVICE,
        reason="需要人工协助。",
    )

    assert case.case_number.startswith("AS-")
    assert case.status == AfterSalesCase.Status.PENDING_REVIEW
    assert case.priority == AfterSalesCase.Priority.NORMAL


@pytest.mark.django_db
def test_pending_confirmation_reports_expiry(verified_user):
    conversation = AgentConversation.objects.create(user=verified_user)
    confirmation = ConfirmationRequest.objects.create(
        conversation=conversation,
        user=verified_user,
        action_type=ConfirmationRequest.ActionType.REFUND_REQUEST,
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    assert confirmation.is_expired is True


@pytest.mark.django_db
def test_customer_memory_is_unique_per_user_type_and_key(verified_user):
    CustomerMemory.objects.create(
        user=verified_user,
        memory_type=CustomerMemory.MemoryType.PREFERENCE,
        key="language",
        value={"value": "zh-CN"},
    )

    with pytest.raises(IntegrityError):
        CustomerMemory.objects.create(
            user=verified_user,
            memory_type=CustomerMemory.MemoryType.PREFERENCE,
            key="language",
            value={"value": "zh-CN"},
        )
