from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.after_sales.knowledge import KnowledgeSearchResult
from apps.authentication.models import User


class StaffKnowledgeManagementAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="knowledge_customer",
            phone_number="+8613800138031",
            password="Demo123!",
        )
        self.staff = User.objects.create_user(
            username="knowledge_staff",
            phone_number="+8613800138032",
            password="Demo123!",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])

    def test_regular_user_cannot_test_knowledge_retrieval(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/v1/after-sales/staff/knowledge-documents/search/",
            {"question": "退货规则是什么？"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    @patch("apps.after_sales.views.search_after_sales_knowledge")
    def test_staff_can_view_retrieval_matches_and_citations(self, mock_search):
        mock_search.return_value = KnowledgeSearchResult(
            matches=[
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "title": "夏季短袖退货规则",
                    "source_label": "售后规则文档",
                    "source_type": "TEXT",
                    "source_url": "",
                    "category": "退货规则",
                    "excerpt": "商品签收后七天内可以申请退货。",
                    "similarity": 0.912,
                    "sequence": 0,
                }
            ],
            requires_human_escalation=False,
            message="已检索到可信售后知识，可据此回答并引用来源。",
        )
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            "/api/v1/after-sales/staff/knowledge-documents/search/",
            {"question": "签收后多久可以退货？", "limit": 5},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["matches"][0]["source_label"], "售后规则文档")
        self.assertEqual(response.data["matches"][0]["chunk_id"], "chunk-1")
        mock_search.assert_called_once_with(
            "签收后多久可以退货？", limit=5, product_id=None, category_id=None
        )
