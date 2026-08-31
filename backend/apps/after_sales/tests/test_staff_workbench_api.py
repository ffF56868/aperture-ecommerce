from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.after_sales.models import AfterSalesCase, AgentConversation, AgentMessage, ToolExecution
from apps.authentication.models import User
from apps.cart_orders.models import Order, OrderItem
from apps.products.models import Category, Product


class StaffAfterSalesWorkbenchAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="staff_workbench_customer",
            phone_number="+8613800138021",
            password="Demo123!",
        )
        self.staff = User.objects.create_user(
            username="staff_workbench_agent",
            phone_number="+8613800138022",
            password="Demo123!",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])
        self.conversation = AgentConversation.objects.create(
            user=self.customer,
            summary="用户反馈商品尺码不合适，希望申请退款。",
        )
        self.after_sales_case = AfterSalesCase.objects.create(
            user=self.customer,
            conversation=self.conversation,
            case_type=AfterSalesCase.CaseType.REFUND,
            reason="尺码不合适",
            agent_summary="订单已核验，符合退款申请条件。",
        )
        AgentMessage.objects.create(
            conversation=self.conversation,
            role=AgentMessage.Role.USER,
            content="我的衣服尺码不合适，想退款。",
        )
        AgentMessage.objects.create(
            conversation=self.conversation,
            role=AgentMessage.Role.ASSISTANT,
            content="我已为你提交退款申请，等待人工审核。",
        )
        AgentMessage.objects.create(
            conversation=self.conversation,
            role=AgentMessage.Role.TOOL,
            content="",
            tool_name="create_after_sales_case",
            tool_arguments={"internal": "not for staff UI"},
        )

    def test_regular_user_cannot_access_staff_queue(self):
        self.client.force_authenticate(self.customer)

        case_response = self.client.get("/api/v1/after-sales/staff/cases/")
        order_response = self.client.get("/api/v1/after-sales/staff/orders/")

        self.assertEqual(case_response.status_code, 403)
        self.assertEqual(order_response.status_code, 403)

    def test_staff_can_view_queue_and_detail_without_tool_messages(self):
        self.client.force_authenticate(self.staff)

        list_response = self.client.get("/api/v1/after-sales/staff/cases/?search=staff_workbench")
        detail_response = self.client.get(
            f"/api/v1/after-sales/staff/cases/{self.after_sales_case.id}/"
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)
        self.assertNotIn("conversation", list_response.data[0])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["user"]["username"], self.customer.username)
        self.assertEqual(
            [message["role"] for message in detail_response.data["conversation"]["messages"]],
            [AgentMessage.Role.USER, AgentMessage.Role.ASSISTANT],
        )

    def test_staff_update_assigns_staff_and_writes_human_audit(self):
        self.client.force_authenticate(self.staff)

        response = self.client.patch(
            f"/api/v1/after-sales/staff/cases/{self.after_sales_case.id}/",
            {"status": AfterSalesCase.Status.IN_REVIEW, "staff_note": "已核对订单，正在处理。"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.after_sales_case.refresh_from_db()
        self.assertEqual(self.after_sales_case.status, AfterSalesCase.Status.IN_REVIEW)
        self.assertEqual(self.after_sales_case.staff_note, "已核对订单，正在处理。")
        self.assertEqual(self.after_sales_case.assigned_to, self.staff)
        self.assertIsNone(self.after_sales_case.resolved_at)
        audit = ToolExecution.objects.get(after_sales_case=self.after_sales_case)
        self.assertEqual(audit.tool_name, "staff_update_after_sales_case")
        self.assertEqual(audit.initiated_by, ToolExecution.Initiator.HUMAN)
        self.assertEqual(audit.agent_role, "staff_workbench")

    def test_approval_sets_resolution_time(self):
        self.client.force_authenticate(self.staff)
        self.after_sales_case.status = AfterSalesCase.Status.IN_REVIEW
        self.after_sales_case.save(update_fields=["status"])

        response = self.client.patch(
            f"/api/v1/after-sales/staff/cases/{self.after_sales_case.id}/",
            {"status": AfterSalesCase.Status.APPROVED},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.after_sales_case.refresh_from_db()
        self.assertEqual(self.after_sales_case.status, AfterSalesCase.Status.APPROVED)
        self.assertIsNotNone(self.after_sales_case.resolved_at)

    def test_invalid_or_empty_update_does_not_change_case(self):
        self.client.force_authenticate(self.staff)
        self.after_sales_case.status = AfterSalesCase.Status.IN_REVIEW
        self.after_sales_case.save(update_fields=["status"])

        invalid_response = self.client.patch(
            f"/api/v1/after-sales/staff/cases/{self.after_sales_case.id}/",
            {"status": AfterSalesCase.Status.CANCELLED},
            format="json",
        )
        empty_response = self.client.patch(
            f"/api/v1/after-sales/staff/cases/{self.after_sales_case.id}/",
            {},
            format="json",
        )

        self.assertEqual(invalid_response.status_code, 409)
        self.assertEqual(invalid_response.data["code"], "INVALID_CASE_TRANSITION")
        self.assertEqual(empty_response.status_code, 400)
        self.after_sales_case.refresh_from_db()
        self.assertEqual(self.after_sales_case.status, AfterSalesCase.Status.IN_REVIEW)

    def test_staff_can_mark_the_paid_order_as_shipped(self):
        category = Category.objects.create(name="工作台发货测试分类")
        product = Product.objects.create(
            category=category,
            name="工作台发货测试商品",
            price=Decimal("59.90"),
            stock_quantity=3,
        )
        order = Order.objects.create(
            user=self.customer,
            status=Order.Status.PAID,
            subtotal=Decimal("59.90"),
            total_amount=Decimal("59.90"),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit_price=Decimal("59.90"),
            quantity=1,
        )
        self.after_sales_case.order = order
        self.after_sales_case.save(update_fields=["order"])
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            f"/api/v1/after-sales/staff/cases/{self.after_sales_case.id}/ship-order/"
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.after_sales_case.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SHIPPED)
        self.assertEqual(self.after_sales_case.assigned_to, self.staff)
        audit = ToolExecution.objects.get(after_sales_case=self.after_sales_case, tool_name="staff_ship_order")
        self.assertEqual(audit.initiated_by, ToolExecution.Initiator.HUMAN)

    def test_staff_cannot_ship_an_order_that_is_not_paid(self):
        order = Order.objects.create(
            user=self.customer,
            status=Order.Status.PENDING,
            subtotal=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )
        self.after_sales_case.order = order
        self.after_sales_case.save(update_fields=["order"])
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            f"/api/v1/after-sales/staff/cases/{self.after_sales_case.id}/ship-order/"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "ORDER_NOT_READY_TO_SHIP")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_staff_can_ship_a_paid_order_without_an_after_sales_case(self):
        order = Order.objects.create(
            user=self.customer,
            status=Order.Status.PAID,
            subtotal=Decimal("99.00"),
            total_amount=Decimal("99.00"),
            shipping_address="北京市朝阳区测试路 1 号",
        )
        self.client.force_authenticate(self.staff)

        list_response = self.client.get("/api/v1/after-sales/staff/orders/")
        ship_response = self.client.post(f"/api/v1/after-sales/staff/orders/{order.id}/ship/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data[0]["id"], str(order.id))
        self.assertEqual(list_response.data[0]["user"]["username"], self.customer.username)
        self.assertEqual(ship_response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SHIPPED)
        self.assertTrue(
            ToolExecution.objects.filter(
                tool_name="staff_ship_order",
                after_sales_case__isnull=True,
                user=self.customer,
            ).exists()
        )

    def test_staff_can_mark_an_approved_return_refund_case_as_refunded(self):
        order = Order.objects.create(
            user=self.customer,
            status=Order.Status.SHIPPED,
            subtotal=Decimal("99.00"),
            total_amount=Decimal("99.00"),
        )
        self.after_sales_case.order = order
        self.after_sales_case.case_type = AfterSalesCase.CaseType.RETURN_REFUND
        self.after_sales_case.status = AfterSalesCase.Status.APPROVED
        self.after_sales_case.save(update_fields=["order", "case_type", "status"])
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            f"/api/v1/after-sales/staff/cases/{self.after_sales_case.id}/refund-order/"
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.after_sales_case.refresh_from_db()
        self.assertEqual(order.status, Order.Status.REFUNDED)
        self.assertEqual(self.after_sales_case.status, AfterSalesCase.Status.CLOSED)
        self.assertEqual(self.after_sales_case.assigned_to, self.staff)
        self.assertIsNotNone(self.after_sales_case.resolved_at)
        self.assertTrue(
            ToolExecution.objects.filter(
                after_sales_case=self.after_sales_case,
                tool_name="staff_refund_order",
                initiated_by=ToolExecution.Initiator.HUMAN,
            ).exists()
        )

    def test_staff_cannot_refund_a_case_before_it_is_approved(self):
        order = Order.objects.create(
            user=self.customer,
            status=Order.Status.PAID,
            subtotal=Decimal("99.00"),
            total_amount=Decimal("99.00"),
        )
        self.after_sales_case.order = order
        self.after_sales_case.case_type = AfterSalesCase.CaseType.REFUND
        self.after_sales_case.status = AfterSalesCase.Status.IN_REVIEW
        self.after_sales_case.save(update_fields=["order", "case_type", "status"])
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            f"/api/v1/after-sales/staff/cases/{self.after_sales_case.id}/refund-order/"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "CASE_NOT_APPROVED_FOR_REFUND")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
