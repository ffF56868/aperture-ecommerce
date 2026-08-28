from decimal import Decimal

from django.test import TestCase, override_settings

from apps.after_sales.models import ToolExecution
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
            {"list_my_orders", "get_my_order_detail", "list_after_sales_policies"},
        )
        self.assertTrue(all(definition["strict"] for definition in definitions))
        self.assertTrue(
            all(
                definition["parameters"].get("additionalProperties") is False
                for definition in definitions
            )
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

    @override_settings(OPENAI_API_KEY="")
    def test_missing_api_key_fails_before_an_sdk_request(self):
        with self.assertRaises(OpenAIConfigurationError):
            get_openai_client()

    @override_settings(OPENAI_API_KEY="sk-test-not-a-real-key")
    def test_configured_key_constructs_the_official_sdk_client_without_a_request(self):
        client = get_openai_client()

        self.assertEqual(client.api_key, "sk-test-not-a-real-key")
