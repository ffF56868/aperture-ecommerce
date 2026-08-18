"""Routes: /api/v1/contact/"""

from django.urls import path

from .views import ContactInquiryCreateView

app_name = "contact"

urlpatterns = [
    path("", ContactInquiryCreateView.as_view(), name="create"),
]
