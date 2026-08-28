"""Declarative rules exposed to the Agent and the frontend."""

from .models import AfterSalesCase


AFTER_SALES_POLICIES = (
    {
        "key": "refund",
        "name": "退款申请",
        "description": "已支付但尚未发货的订单，可以提交退款审核申请。",
        "eligible_order_statuses": ("PAID",),
        "requires_confirmation": True,
        "confirmation_action": "REFUND_REQUEST",
        "case_type": AfterSalesCase.CaseType.REFUND,
    },
    {
        "key": "return-refund",
        "name": "退货退款申请",
        "description": "已支付或已发货的订单，可以提交退货退款审核申请。",
        "eligible_order_statuses": ("PAID", "SHIPPED"),
        "requires_confirmation": True,
        "confirmation_action": "RETURN_REFUND_REQUEST",
        "case_type": AfterSalesCase.CaseType.RETURN_REFUND,
    },
    {
        "key": "cancel-order",
        "name": "取消待支付订单",
        "description": "仅待支付订单可由用户确认后取消。",
        "eligible_order_statuses": ("PENDING",),
        "requires_confirmation": True,
        "confirmation_action": "CANCEL_ORDER",
        "case_type": None,
    },
    {
        "key": "quality-issue",
        "name": "质量问题",
        "description": "已支付或已发货订单可提交质量问题工单，由人工审核处理。",
        "eligible_order_statuses": ("PAID", "SHIPPED"),
        "requires_confirmation": False,
        "confirmation_action": None,
        "case_type": AfterSalesCase.CaseType.QUALITY_ISSUE,
    },
    {
        "key": "delivery-issue",
        "name": "物流异常",
        "description": "仅已发货订单可提交物流异常工单。",
        "eligible_order_statuses": ("SHIPPED",),
        "requires_confirmation": False,
        "confirmation_action": None,
        "case_type": AfterSalesCase.CaseType.DELIVERY_ISSUE,
    },
    {
        "key": "human-service",
        "name": "人工服务",
        "description": "任意订单状态均可转接人工服务。",
        "eligible_order_statuses": ("PENDING", "PAID", "SHIPPED", "CANCELLED"),
        "requires_confirmation": False,
        "confirmation_action": None,
        "case_type": AfterSalesCase.CaseType.HUMAN_SERVICE,
    },
)


def get_policy(policy_key: str):
    """Return one policy by its stable public key, or None when unknown."""

    return next((policy for policy in AFTER_SALES_POLICIES if policy["key"] == policy_key), None)
