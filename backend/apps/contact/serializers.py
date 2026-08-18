from rest_framework import serializers

from .models import ContactInquiry


class ContactInquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactInquiry
        fields = ("id", "full_name", "email", "phone_number", "subject", "message", "created_at")
        read_only_fields = ("id", "created_at")

    def create(self, validated_data):
        inquiry = super().create(validated_data)
        from .tasks import notify_new_contact_inquiry

        notify_new_contact_inquiry.delay(inquiry.id)
        return inquiry
