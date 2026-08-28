from decimal import Decimal

from django.test import TestCase, override_settings

from apps.after_sales.models import AfterSalesCase, AgentConversation, ConfirmationRequest, ToolExecution
from apps.after_sales.openai_client import OpenAIConfigurationError, get_openai_client
from apps.after_sales.tools import ToolContext, execute_tool, get_openai_tool_definitions
from apps.authentication.models import User
from apps.cart_orders.models import Order, OrderItem, Payment


class AfterSalesToolTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tool_owner",
            phone_number="+8613800138003",
            password="Demo123!",
        )
        self.other_user = User.objects.create_user(
            username="tool_other_user",
            phone_number="+8613800138004",
            password="Demo123!",
        )
        self.order = self._create_order(self.user, "我的测试短袖")
        self.other_order = self._create_order(self.other_user, "其他用户的订单")
        self.context = ToolContext(user=self.user)
        self.conversation = AgentConversation.objects.create(user=self.user)
        self.write_context = ToolContext(
            user=self.user,
            conversation=self.conversation,
            allowed_action_kinds=frozenset(
                {ToolExecution.ActionKind.READ, ToolExecution.ActionKind.WRITE}
            ),
        )

    def _create_order(self, user, product_name):
        order = Order.objects.create(
            user=user,
            status=Order.Status.PAID,
            subtotal=Decimal("59.90"),
            tax_amount=Decimal("0.00"),
            shipping_amount=Decimal("0.00"),
            total_amount=Decimal("59.90"),
        )
        OrderItem.objects.create(
            order=order,
            product=None,
            product_name=product_name,
            unit_price=Decimal("59.90"),
            quantity=1,
        )
        Payment.objects.create(
            order=order,
            transaction_id=f"tool_test_{order.id.hex[:20]}",
            amount=order.total_amount,
            status=Payment.Status.SUCCESS,
        )
        return order

    def test_definitions_are_strict_and_only_expose_allowlisted_tools(self):
        definitions = get_openai_tool_definitions()

        self.assertEqual(
            {definition["name"] for definition in definitions},
            {
                "list_my_orders",
                "get_my_order_detail",
                "list_after_sales_policies",
                "list_my_after_sales_cases",
                "prepare_after_sales_confirmation",
                "create_after_sales_case",
            },
        )
        self.assertTrue(all(definition["strict"] for definition in definitions))
        self.assertTrue(
            all(
                definition["parameters"].get("additionalProperties") is False
                for definition in definitions
            )
        )
        create_case_definition = next(
            definition for definition in definitions if definition["name"] == "create_after_sales_case"
        )
        self.assertEqual(
            set(create_case_definition["parameters"]["required"]),
            set(create_case_definition["parameters"]["properties"]),
        )

    def test_list_orders_returns_only_the_current_users_orders(self):
        result = execute_tool(self.context, "list_my_orders", {})

        self.assertTrue(result["ok"])
        self.assertEqual([order["id"] for order in result["data"]["orders"]], [str(self.order.id)])
        execution = ToolExecution.objects.get()
        self.assertEqual(execution.status, ToolExecution.Status.SUCCEEDED)

    def test_other_users_order_is_not_disclosed(self):
        result = execute_tool(
            self.context,
            "get_my_order_detail",
            {"order_id": str(self.other_order.id)},
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "ORDER_NOT_FOUND")
        self.assertEqual(ToolExecution.objects.get().error_code, "ORDER_NOT_FOUND")

    def test_extra_arguments_are_rejected(self):
        result = execute_tool(
            self.context,
            "get_my_order_detail",
            {"order_id": str(self.order.id), "include_all_users": True},
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "INVALID_ARGUMENTS")

    def test_unregistered_tool_is_denied_and_audited(self):
        result = execute_tool(self.context, "run_sql", {"sql": "SELECT * FROM auth_users"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TOOL_NOT_ALLOWED")
        execution = ToolExecution.objects.get()
        self.assertEqual(execution.status, ToolExecution.Status.DENIED)
        self.assertEqual(execution.tool_name, "run_sql")

    def test_context_permission_denial_is_audited(self):
        result = execute_tool(
            ToolContext(user=self.user, allowed_action_kinds=frozenset()),
            "list_my_orders",
            {},
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TOOL_PERMISSION_DENIED")
        self.assertEqual(ToolExecution.objects.get().status, ToolExecution.Status.DENIED)

    def test_tool_is_denied_when_its_specialist_is_not_in_the_collaboration_plan(self):
        result = execute_tool(
            ToolContext(
                user=self.user,
                allowed_agent_roles=frozenset({"policy_advisor"}),
            ),
            "list_my_orders",
            {},
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "AGENT_ROLE_DENIED")
        execution = ToolExecution.objects.get()
        self.assertEqual(execution.status, ToolExecution.Status.DENIED)
        self.assertEqual(execution.agent_role, "order_analyst")

    def test_refund_tool_prepares_confirmation_without_creating_a_case_or_refund(self):
        result = execute_tool(
            self.write_context,
            "prepare_after_sales_confirmation",
            {
                "order_id": str(self.order.id),
                "policy_key": "refund",
                "reason": "尺码不合适",
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(ConfirmationRequest.objects.count(), 1)
        self.assertEqual(AfterSalesCase.objects.count(), 0)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(result["data"]["confirmation"]["status"], ConfirmationRequest.Status.PENDING)
        execution = ToolExecution.objects.get()
        self.assertEqual(execution.action_kind, ToolExecution.ActionKind.WRITE)
        self.assertEqual(execution.status, ToolExecution.Status.SUCCEEDED)

    def test_default_read_context_cannot_prepare_a_confirmation(self):
        result = execute_tool(
            ToolContext(user=self.user, conversation=self.conversation),
            "prepare_after_sales_confirmation",
            {
                "order_id": str(self.order.id),
                "policy_key": "refund",
                "reason": "尺码不合适",
            },
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TOOL_PERMISSION_DENIED")
        self.assertEqual(ConfirmationRequest.objects.count(), 0)

    def test_quality_issue_creates_one_high_priority_case(self):
        result = execute_tool(
            self.write_context,
            "create_after_sales_case",
            {
                "order_id": str(self.order.id),
                "policy_key": "quality-issue",
                "reason": "衣服有明显破损",
            },
        )

        self.assertTrue(result["ok"])
        after_sales_case = AfterSalesCase.objects.get()
        self.assertEqual(after_sales_case.case_type, AfterSalesCase.CaseType.QUALITY_ISSUE)
        self.assertEqual(after_sales_case.priority, AfterSalesCase.Priority.HIGH)
        self.assertEqual(after_sales_case.status, AfterSalesCase.Status.PENDING_REVIEW)

    def test_human_service_can_create_a_case_without_an_order(self):
        result = execute_tool(
            self.write_context,
            "create_after_sales_case",
            {"policy_key": "human-service", "reason": "我想找人工客服处理", "order_id": None},
        )

        self.assertTrue(result["ok"])
        after_sales_case = AfterSalesCase.objects.get()
        self.assertIsNone(after_sales_case.order)
        self.assertEqual(after_sales_case.case_type, AfterSalesCase.CaseType.HUMAN_SERVICE)

    def test_human_service_accepts_explicit_null_order_id_for_strict_schema(self):
        result = execute_tool(
            self.write_context,
            "create_after_sales_case",
            {"policy_key": "human-service", "reason": "需要人工客服", "order_id": None},
        )

        self.assertTrue(result["ok"])

    @override_settings(OPENAI_API_KEY="")
    def test_missing_api_key_fails_before_an_sdk_request(self):
        with self.assertRaises(OpenAIConfigurationError):
            get_openai_client()

    @override_settings(OPENAI_API_KEY="sk-test-not-a-real-key")
    def test_configured_key_constructs_the_official_sdk_client_without_a_request(self):
        client = get_openai_client()

        self.assertEqual(client.api_key, "sk-test-not-a-real-key")
