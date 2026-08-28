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


class AgentConversationTurnSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    state = serializers.CharField()
    assistant_message = serializers.CharField()
    tool_calls = AgentToolCallSerializer(many=True)


class AgentConversationDetailSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    state = serializers.CharField()
    messages = AgentMessageHistorySerializer(many=True)
