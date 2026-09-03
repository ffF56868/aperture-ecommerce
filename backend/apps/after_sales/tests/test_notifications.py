from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.after_sales.models import AfterSalesCase, AfterSalesNotification, AgentConversation
from apps.after_sales.notifications import create_case_notification
from apps.after_sales.tasks import send_after_sales_notification_email
from apps.after_sales.workflow import create_automatic_case, update_staff_case
from apps.authentication.models import User


class AfterSalesNotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="notification_customer",
            phone_number="+8613800138091",
            password="Demo123!",
        )
        self.other_customer = User.objects.create_user(
            username="notification_other_customer",
            phone_number="+8613800138092",
            password="Demo123!",
        )
        self.staff = User.objects.create_user(
            username="notification_staff",
            phone_number="+8613800138093",
            password="Demo123!",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])
        self.conversation = AgentConversation.objects.create(user=self.customer)

    def _create_case(self, *, user=None, conversation=None, case_type=None):
        return AfterSalesCase.objects.create(
            user=user or self.customer,
            conversation=conversation or self.conversation,
            case_type=case_type or AfterSalesCase.CaseType.QUALITY_ISSUE,
            reason="商品存在问题，需要售后处理。",
        )

    def test_case_creation_emits_one_notification_and_enqueues_email_after_commit(self):
        with patch("apps.after_sales.tasks.send_after_sales_notification_email.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                case, reused = create_automatic_case(
                    user=self.customer,
                    conversation=self.conversation,
                    policy_key="human-service",
                    reason="需要人工协助。",
                )

            self.assertFalse(reused)
            notification = AfterSalesNotification.objects.get(after_sales_case=case)
            self.assertEqual(notification.event_type, AfterSalesNotification.EventType.CASE_CREATED)
            delay.assert_called_once_with(str(notification.id))

            create_case_notification(case, AfterSalesNotification.EventType.CASE_CREATED)
            self.assertEqual(
                AfterSalesNotification.objects.filter(after_sales_case=case).count(), 1
            )

    def test_staff_lifecycle_emits_approval_rejection_and_more_info_notifications(self):
        case = self._create_case()

        update_staff_case(
            staff_user=self.staff,
            case_id=case.id,
            status=AfterSalesCase.Status.IN_REVIEW,
        )
        update_staff_case(
            staff_user=self.staff,
            case_id=case.id,
            status=AfterSalesCase.Status.NEED_CUSTOMER_INFO,
            staff_note="请补充商品照片。",
        )
        update_staff_case(
            staff_user=self.staff,
            case_id=case.id,
            status=AfterSalesCase.Status.IN_REVIEW,
        )
        update_staff_case(
            staff_user=self.staff,
            case_id=case.id,
            status=AfterSalesCase.Status.APPROVED,
            staff_note="资料已核验。",
        )

        rejected_case = self._create_case()
        update_staff_case(
            staff_user=self.staff,
            case_id=rejected_case.id,
            status=AfterSalesCase.Status.REJECTED,
            staff_note="暂不符合售后规则。",
        )

        self.assertEqual(
            set(
                AfterSalesNotification.objects.filter(user=self.customer).values_list(
                    "event_type", flat=True
                )
            ),
            {
                AfterSalesNotification.EventType.NEED_CUSTOMER_INFO,
                AfterSalesNotification.EventType.CASE_APPROVED,
                AfterSalesNotification.EventType.CASE_REJECTED,
            },
        )

    def test_notification_list_and_read_actions_are_owner_scoped(self):
        own_case = self._create_case()
        other_conversation = AgentConversation.objects.create(user=self.other_customer)
        other_case = self._create_case(
            user=self.other_customer,
            conversation=other_conversation,
        )
        own_notification, _ = create_case_notification(
            own_case, AfterSalesNotification.EventType.CASE_CREATED
        )
        other_notification, _ = create_case_notification(
            other_case, AfterSalesNotification.EventType.CASE_CREATED
        )

        self.client.force_authenticate(self.customer)
        list_response = self.client.get("/api/v1/after-sales/notifications/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["unread_count"], 1)
        self.assertEqual(
            [item["id"] for item in list_response.data["notifications"]],
            [str(own_notification.id)],
        )

        forbidden_read = self.client.post(
            f"/api/v1/after-sales/notifications/{other_notification.id}/read/"
        )
        self.assertEqual(forbidden_read.status_code, 404)

        read_response = self.client.post(
            f"/api/v1/after-sales/notifications/{own_notification.id}/read/"
        )
        self.assertEqual(read_response.status_code, 200)
        self.assertTrue(read_response.data["is_read"])

        read_again_response = self.client.post(
            f"/api/v1/after-sales/notifications/{own_notification.id}/read/"
        )
        self.assertEqual(read_again_response.status_code, 200)
        self.assertEqual(
            AfterSalesNotification.objects.filter(user=self.customer, is_read=False).count(), 0
        )

    def test_mark_all_notifications_read_only_updates_current_user(self):
        own_case = self._create_case()
        other_conversation = AgentConversation.objects.create(user=self.other_customer)
        other_case = self._create_case(
            user=self.other_customer,
            conversation=other_conversation,
        )
        create_case_notification(own_case, AfterSalesNotification.EventType.CASE_CREATED)
        create_case_notification(other_case, AfterSalesNotification.EventType.CASE_CREATED)

        self.client.force_authenticate(self.customer)
        response = self.client.post("/api/v1/after-sales/notifications/read-all/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated_count"], 1)
        self.assertEqual(
            AfterSalesNotification.objects.filter(user=self.customer, is_read=False).count(), 0
        )
        self.assertEqual(
            AfterSalesNotification.objects.filter(user=self.other_customer, is_read=False).count(),
            1,
        )

    def test_email_task_marks_sent_or_skipped(self):
        self.customer.email = "customer@example.com"
        self.customer.save(update_fields=["email"])
        sent_case = self._create_case()
        sent_notification, _ = create_case_notification(
            sent_case, AfterSalesNotification.EventType.CASE_CREATED
        )

        sent_result = send_after_sales_notification_email.run(str(sent_notification.id))
        sent_notification.refresh_from_db()
        self.assertEqual(sent_result["status"], "sent")
        self.assertEqual(sent_notification.email_status, AfterSalesNotification.EmailStatus.SENT)
        self.assertIsNotNone(sent_notification.email_sent_at)

        no_email_customer = User.objects.create_user(
            username="notification_no_email_customer",
            phone_number="+8613800138094",
            password="Demo123!",
        )
        no_email_conversation = AgentConversation.objects.create(user=no_email_customer)
        skipped_case = self._create_case(
            user=no_email_customer,
            conversation=no_email_conversation,
        )
        skipped_notification, _ = create_case_notification(
            skipped_case, AfterSalesNotification.EventType.CASE_CREATED
        )
        skipped_result = send_after_sales_notification_email.run(str(skipped_notification.id))
        skipped_notification.refresh_from_db()
        self.assertEqual(skipped_result["status"], "skipped")
        self.assertEqual(skipped_notification.email_status, AfterSalesNotification.EmailStatus.SKIPPED)
