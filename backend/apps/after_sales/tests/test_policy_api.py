from django.test import TestCase
from rest_framework.test import APIClient

from apps.authentication.models import User


class AfterSalesPolicyAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="policy_api_user",
            phone_number="+8613800138002",
            password="Demo123!",
        )

    def test_policy_list_requires_login(self):
        response = self.client.get("/api/v1/after-sales/policies/")

        self.assertEqual(response.status_code, 401)

    def test_policy_list_returns_the_agent_rules(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/after-sales/policies/")

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 6)

    def test_return_refund_policy_requires_confirmation(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/after-sales/policies/return-refund/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["case_type"], "RETURN_REFUND")
        self.assertTrue(response.data["requires_confirmation"])

    def test_unknown_policy_returns_not_found(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/after-sales/policies/not-a-policy/")

        self.assertEqual(response.status_code, 404)
