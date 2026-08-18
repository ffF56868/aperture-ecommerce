"""Contact inquiry model — stores messages submitted through the public Contact Us form."""

from django.core.validators import EmailValidator
from django.db import models

from core.mixins import TimeStampedMixin


class ContactInquiry(TimeStampedMixin):
    """A message submitted through the public contact form."""

    full_name = models.CharField(max_length=150)
    email = models.EmailField(validators=[EmailValidator()])
    phone_number = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Contact Inquiry"
        verbose_name_plural = "Contact Inquiries"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.full_name} — {self.subject}"
