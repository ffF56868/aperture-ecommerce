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


class AfterSalesNotificationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    event_type = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    action_url = serializers.CharField()
    is_read = serializers.BooleanField()
    read_at = serializers.DateTimeField(allow_null=True)
    email_status = serializers.CharField()
    created_at = serializers.DateTimeField()
    case_number = serializers.CharField(allow_null=True)


class AfterSalesNotificationListSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()
    notifications = AfterSalesNotificationSerializer(many=True)


class AfterSalesNotificationReadAllSerializer(serializers.Serializer):
    updated_count = serializers.IntegerField()
    read_at = serializers.DateTimeField()


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


class AgentRunEventSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    event_type = serializers.CharField()
    status = serializers.CharField()
    sequence = serializers.IntegerField()
    name = serializers.CharField()
    detail = serializers.DictField()
    duration_ms = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()


class AgentRunSummarySerializer(serializers.Serializer):
    total_runs = serializers.IntegerField()
    completed_runs = serializers.IntegerField()
    failed_runs = serializers.IntegerField()
    blocked_runs = serializers.IntegerField()
    escalated_runs = serializers.IntegerField()
    awaiting_confirmation_runs = serializers.IntegerField()
    success_rate = serializers.FloatField()
    average_duration_ms = serializers.IntegerField()
    total_tool_calls = serializers.IntegerField()
    failed_tool_calls = serializers.IntegerField()
    denied_tool_calls = serializers.IntegerField()
    total_tokens = serializers.IntegerField(allow_null=True)


class AgentRunListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    conversation_id = serializers.UUIDField(allow_null=True)
    user = StaffCustomerSerializer(allow_null=True)
    model_name = serializers.CharField()
    current_intent = serializers.CharField()
    input_preview = serializers.CharField()
    status = serializers.CharField()
    status_label = serializers.CharField()
    tool_rounds = serializers.IntegerField()
    tool_call_count = serializers.IntegerField()
    successful_tool_count = serializers.IntegerField()
    failed_tool_count = serializers.IntegerField()
    denied_tool_count = serializers.IntegerField()
    total_tokens = serializers.IntegerField(allow_null=True)
    duration_ms = serializers.IntegerField(allow_null=True)
    started_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True)


class AgentRunListResponseSerializer(serializers.Serializer):
    summary = AgentRunSummarySerializer()
    runs = AgentRunListItemSerializer(many=True)


class AgentRunToolExecutionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tool_name = serializers.CharField()
    agent_role = serializers.CharField()
    action_kind = serializers.CharField()
    status = serializers.CharField()
    initiated_by = serializers.CharField()
    sanitized_arguments = serializers.DictField()
    result = serializers.DictField()
    error_code = serializers.CharField()
    duration_ms = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()


class AgentRunDetailSerializer(AgentRunListItemSerializer):
    input_message = serializers.CharField()
    assistant_message = serializers.CharField()
    agent_roles = serializers.ListField(child=serializers.DictField())
    failure_code = serializers.CharField()
    failure_message = serializers.CharField()
    response_id = serializers.CharField()
    confirmation_request_id = serializers.UUIDField(allow_null=True)
    events = AgentRunEventSerializer(many=True)
    tool_executions = AgentRunToolExecutionSerializer(many=True)


class AgentEvaluationMetricSerializer(serializers.Serializer):
    passed = serializers.IntegerField(required=False)
    total = serializers.IntegerField(required=False)
    failed = serializers.IntegerField(required=False)
    rate = serializers.FloatField(required=False)
    value = serializers.IntegerField(required=False)
    unit = serializers.CharField(required=False)


class AgentEvaluationCaseResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    case_id = serializers.CharField()
    category = serializers.CharField()
    description = serializers.CharField()
    message = serializers.CharField()
    expected_intent = serializers.CharField()
    actual_intent = serializers.CharField()
    expected_tools = serializers.ListField(child=serializers.CharField())
    actual_tools = serializers.ListField(child=serializers.CharField())
    expected_arguments = serializers.ListField(child=serializers.DictField())
    actual_arguments = serializers.ListField(child=serializers.DictField())
    passed = serializers.BooleanField()
    intent_passed = serializers.BooleanField()
    tool_selection_passed = serializers.BooleanField()
    parameter_applicable = serializers.BooleanField()
    parameter_passed = serializers.BooleanField(allow_null=True)
    authorization_passed = serializers.BooleanField()
    unauthorized_case = serializers.BooleanField()
    unauthorized_blocked = serializers.BooleanField()
    dangerous_case = serializers.BooleanField()
    dangerous_blocked = serializers.BooleanField()
    response_compliance_passed = serializers.BooleanField()
    human_escalated = serializers.BooleanField()
    failed = serializers.BooleanField()
    response_time_ms = serializers.IntegerField()
    actual_error_codes = serializers.ListField(child=serializers.CharField())
    assistant_message = serializers.CharField()
    failures = serializers.ListField(child=serializers.CharField())


class AgentEvaluationRunListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    status_label = serializers.CharField()
    trigger = serializers.CharField()
    trigger_label = serializers.CharField()
    mode = serializers.CharField()
    started_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True)
    total_cases = serializers.IntegerField()
    passed_cases = serializers.IntegerField()
    failed_cases = serializers.IntegerField()
    average_response_ms = serializers.IntegerField()


class AgentEvaluationSummarySerializer(serializers.Serializer):
    total_runs = serializers.IntegerField()
    latest_run_id = serializers.UUIDField(allow_null=True)
    latest_started_at = serializers.DateTimeField(allow_null=True)


class AgentEvaluationRunListResponseSerializer(serializers.Serializer):
    summary = AgentEvaluationSummarySerializer()
    runs = AgentEvaluationRunListItemSerializer(many=True)


class AgentEvaluationRunDetailSerializer(AgentEvaluationRunListItemSerializer):
    metrics = serializers.DictField(child=AgentEvaluationMetricSerializer())
    cases = AgentEvaluationCaseResultSerializer(many=True)
    error_message = serializers.CharField()
