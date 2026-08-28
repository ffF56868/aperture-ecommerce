from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.after_sales.models import AgentConversation, AgentMessage, ConfirmationRequest, ToolExecution
from apps.after_sales.openai_client import OpenAIConfigurationError
from apps.authentication.models import User
from apps.cart_orders.models import Order, OrderItem


class FakeResponses:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("Unexpected extra Responses API request")
        return self.responses.pop(0)


class FakeOpenAIClient:
    def __init__(self, responses):
        self.responses = FakeResponses(responses)


def text_response(text, response_id="resp_text"):
    return SimpleNamespace(id=response_id, output=[], output_text=text)


def function_call_response(name, arguments, call_id="call_test", response_id="resp_tool"):
    return SimpleNamespace(
        id=response_id,
        output=[
            SimpleNamespace(
                type="function_call",
                name=name,
                arguments=arguments,
                call_id=call_id,
            )
        ],
        output_text="",
    )


class AfterSalesAgentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="agent_owner",
            phone_number="+8613800138004",
            password="Demo123!",
        )
        self.other_user = User.objects.create_user(
            username="agent_other",
            phone_number="+8613800138005",
            password="Demo123!",
        )
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal("59.90"),
            total_amount=Decimal("59.90"),
        )
        OrderItem.objects.create(
            order=self.order,
            product_name="测试短袖",
            unit_price=Decimal("59.90"),
            quantity=1,
        )
        self.client.force_authenticate(self.user)

    @patch("apps.after_sales.agent_service.get_openai_client")
    def test_message_runs_allowlisted_tool_and_persists_auditable_turn(self, mock_get_client):
        fake_client = FakeOpenAIClient(
            [
                function_call_response("list_my_orders", "{}"),
                text_response("我查到了你最近的订单，当前状态为待支付。", "resp_final"),
            ]
        )
        mock_get_client.return_value = fake_client

        response = self.client.post(
            "/api/v1/after-sales/conversations/", {"message": "帮我查询最近订单"}, format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["assistant_message"], "我查到了你最近的订单，当前状态为待支付。")
        self.assertEqual(response.data["tool_calls"], [{"tool_name": "list_my_orders", "ok": True}])
        self.assertEqual(
            response.data["collaboration_plan"],
            [
                {
                    "key": "order_analyst",
                    "label": "订单核验专员",
                    "responsibility": "只核验当前用户自己的订单、商品、支付和发货状态。",
                }
            ],
        )
        self.assertEqual(len(fake_client.responses.calls), 2)
        self.assertEqual(fake_client.responses.calls[0]["tool_choice"], "auto")
        self.assertEqual(fake_client.responses.calls[1]["previous_response_id"], "resp_tool")
        self.assertEqual(
            fake_client.responses.calls[1]["input"][0]["type"], "function_call_output"
        )

        conversation = AgentConversation.objects.get(id=response.data["conversation_id"])
        self.assertEqual(conversation.user, self.user)
        self.assertEqual(conversation.current_intent, "ORDER_QUERY")
        self.assertEqual(conversation.messages.count(), 3)
        self.assertEqual(
            conversation.messages.filter(role=AgentMessage.Role.TOOL).get().tool_name,
            "list_my_orders",
        )
        self.assertEqual(ToolExecution.objects.get().status, ToolExecution.Status.SUCCEEDED)
        self.assertEqual(ToolExecution.objects.get().agent_role, "order_analyst")

        detail_response = self.client.get(
            f"/api/v1/after-sales/conversations/{response.data['conversation_id']}/"
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["collaboration_plan"][0]["key"], "order_analyst")

    @patch("apps.after_sales.agent_service.get_openai_client")
    def test_message_without_tool_returns_direct_reply(self, mock_get_client):
        fake_client = FakeOpenAIClient([text_response("请告诉我需要核验的订单或售后问题。")])
        mock_get_client.return_value = fake_client

        response = self.client.post(
            "/api/v1/after-sales/conversations/", {"message": "你好"}, format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["tool_calls"], [])
        self.assertEqual(AgentMessage.objects.filter(role=AgentMessage.Role.TOOL).count(), 0)
        self.assertEqual(len(fake_client.responses.calls), 1)

    def test_conversation_history_is_private_to_its_owner(self):
        conversation = AgentConversation.objects.create(user=self.user)
        AgentMessage.objects.create(
            conversation=conversation,
            role=AgentMessage.Role.USER,
            content="这是私有售后内容。",
        )
        self.client.force_authenticate(self.other_user)

        response = self.client.get(f"/api/v1/after-sales/conversations/{conversation.id}/")

        self.assertEqual(response.status_code, 404)

    @patch("apps.after_sales.agent_service.get_openai_client")
    def test_model_configuration_failure_returns_safe_service_unavailable(self, mock_get_client):
        mock_get_client.side_effect = OpenAIConfigurationError("secret configuration detail")

        response = self.client.post(
            "/api/v1/after-sales/conversations/", {"message": "查询订单"}, format="json"
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "智能售后服务暂时不可用，请稍后重试。")
        self.assertEqual(AgentMessage.objects.count(), 0)
        self.assertEqual(AgentConversation.objects.count(), 0)

    @patch("apps.after_sales.agent_service.get_openai_client")
    def test_tool_round_limit_stops_before_a_fourth_model_request(self, mock_get_client):
        fake_client = FakeOpenAIClient(
            [
                function_call_response("list_after_sales_policies", "{}", "call_1", "resp_1"),
                function_call_response("list_after_sales_policies", "{}", "call_2", "resp_2"),
                function_call_response("list_after_sales_policies", "{}", "call_3", "resp_3"),
            ]
        )
        mock_get_client.return_value = fake_client

        response = self.client.post(
            "/api/v1/after-sales/conversations/", {"message": "售后规则"}, format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("查询步骤较多", response.data["assistant_message"])
        self.assertEqual(len(fake_client.responses.calls), 3)
        self.assertEqual(ToolExecution.objects.count(), 3)

    @patch("apps.after_sales.agent_service.get_openai_client")
    def test_agent_can_prepare_but_not_execute_a_refund_request(self, mock_get_client):
        self.order.status = Order.Status.PAID
        self.order.save(update_fields=["status"])
        fake_client = FakeOpenAIClient(
            [
                function_call_response(
                    "prepare_after_sales_confirmation",
                    (
                        '{"order_id":"%s","policy_key":"refund",'
                        '"reason":"尺码不合适"}' % self.order.id
                    ),
                ),
                text_response("我已生成退款申请，请在右侧确认后提交。", "resp_final"),
            ]
        )
        mock_get_client.return_value = fake_client

        response = self.client.post(
            "/api/v1/after-sales/conversations/", {"message": "这件衣服尺码不合适，申请退款"}, format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["state"], AgentConversation.State.AWAITING_CONFIRMATION)
        self.assertEqual(
            [item["key"] for item in response.data["collaboration_plan"]],
            ["order_analyst", "policy_advisor", "workflow_specialist"],
        )
        self.assertEqual(response.data["pending_confirmation"]["status"], ConfirmationRequest.Status.PENDING)
        self.assertEqual(ConfirmationRequest.objects.count(), 1)
        self.assertEqual(len(fake_client.responses.calls), 2)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
