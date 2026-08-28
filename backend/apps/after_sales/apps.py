from django.apps import AppConfig


class AfterSalesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.after_sales"
    label = "after_sales"
    verbose_name = "售后 Agent"
