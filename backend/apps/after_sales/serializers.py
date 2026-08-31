"""Serializers for public after-sales policy and conversation APIs."""

from rest_framework import serializers


class AfterSalesPolicySerializer(serializers.Serializer):
    key = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    eligible_order_statuses = serializers.ListField(child=serializers.CharField())
    requires_confirmation = serializers.BooleanField()
    confirmation_action = serializers.CharField(allow_null=True)
    case_type = serializers.CharField(allow_null=True)


class ConversationMessageRequestSerializer(serializers.Serializer):
    """Validate one bounded customer message for the Agent."""

    message = serializers.CharField(max_length=2000, trim_whitespace=True)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_message(self, value):
        if not value:
            raise serializers.ValidationError("消息不能为空。")
        return value


class AgentMessageHistorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    role = serializers.CharField()
    content = serializers.CharField()
    created_at = serializers.DateTimeField()


class AgentToolCallSerializer(serializers.Serializer):
    tool_name = serializers.CharField()
    ok = serializers.BooleanField()


class AgentCollaborationRoleSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    responsibility = serializers.CharField()


class AfterSalesOrderSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    items = serializers.ListField(child=serializers.DictField())


class ConfirmationResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    action_type = serializers.CharField()
    action_label = serializers.CharField()
    policy_key = serializers.CharField()
    policy_name = serializers.CharField()
    reason = serializers.CharField()
    order = AfterSalesOrderSummarySerializer(allow_null=True)
    expires_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()


class AfterSalesCaseResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    case_number = serializers.CharField()
    case_type = serializers.CharField()
    case_type_label = serializers.CharField()
    status = serializers.CharField()
    status_label = serializers.CharField()
    priority = serializers.CharField()
    reason = serializers.CharField()
    order = AfterSalesOrderSummarySerializer(allow_null=True)
    created_at = serializers.DateTimeField()


class AgentConversationTurnSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    state = serializers.CharField()
    assistant_message = serializers.CharField()
    tool_calls = AgentToolCallSerializer(many=True)
    collaboration_plan = AgentCollaborationRoleSerializer(many=True)
    pending_confirmation = ConfirmationResponseSerializer(allow_null=True)
    recent_cases = AfterSalesCaseResponseSerializer(many=True)


class AgentConversationDetailSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    state = serializers.CharField()
    messages = AgentMessageHistorySerializer(many=True)
    collaboration_plan = AgentCollaborationRoleSerializer(many=True)
    pending_confirmation = ConfirmationResponseSerializer(allow_null=True)
    recent_cases = AfterSalesCaseResponseSerializer(many=True)


class ConfirmationExecutionSerializer(serializers.Serializer):
    confirmation = ConfirmationResponseSerializer()
    after_sales_case = AfterSalesCaseResponseSerializer(allow_null=True)
    already_executed = serializers.BooleanField()
    message = serializers.CharField()


class ConfirmationRejectionSerializer(serializers.Serializer):
    confirmation = ConfirmationResponseSerializer()
    message = serializers.CharField()


class StaffCustomerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    phone_number = serializers.CharField()


class StaffAssigneeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class StaffConversationMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    role = serializers.CharField()
    content = serializers.CharField()
    created_at = serializers.DateTimeField()


class StaffConversationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    state = serializers.CharField()
    summary = serializers.CharField()
    messages = StaffConversationMessageSerializer(many=True)


class StaffAfterSalesCaseSerializer(AfterSalesCaseResponseSerializer):
    updated_at = serializers.DateTimeField()
    resolved_at = serializers.DateTimeField(allow_null=True)
    agent_summary = serializers.CharField()
    staff_note = serializers.CharField()
    user = StaffCustomerSerializer()
    assigned_to = StaffAssigneeSerializer(allow_null=True)
    conversation = StaffConversationSerializer(allow_null=True, required=False)


class StaffAfterSalesCaseUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=(
        "PENDING_REVIEW",
        "IN_REVIEW",
        "NEED_CUSTOMER_INFO",
        "APPROVED",
        "REJECTED",
        "CLOSED",
        "CANCELLED",
    ), required=False)
    staff_note = serializers.CharField(max_length=2000, allow_blank=True, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("请提交处理状态或客服备注。")
        return attrs


class StaffOrderItemSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2)


class StaffOrderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    status_label = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    shipping_address = serializers.CharField()
    user = StaffCustomerSerializer()
    items = StaffOrderItemSerializer(many=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
