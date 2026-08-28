"""Serializers for the public after-sales policy API."""

from rest_framework import serializers


class AfterSalesPolicySerializer(serializers.Serializer):
    key = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    eligible_order_statuses = serializers.ListField(child=serializers.CharField())
    requires_confirmation = serializers.BooleanField()
    confirmation_action = serializers.CharField(allow_null=True)
    case_type = serializers.CharField(allow_null=True)
