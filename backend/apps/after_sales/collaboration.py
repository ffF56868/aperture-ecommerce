"""Deterministic specialist routing for the after-sales Agent."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Specialist:
    """One narrowly scoped worker available to the coordinator."""

    key: str
    label: str
    responsibility: str
    tool_names: tuple[str, ...]


SPECIALISTS = {
    "order_analyst": Specialist(
        key="order_analyst",
        label="订单核验专员",
        responsibility="只核验当前用户自己的订单、商品、支付和发货状态。",
        tool_names=("list_my_orders", "get_my_order_detail"),
    ),
    "policy_advisor": Specialist(
        key="policy_advisor",
        label="售后规则专员",
        responsibility="只解释已配置的售后规则，不承诺退款或审核结果。",
        tool_names=("list_after_sales_policies",),
    ),
    "case_tracker": Specialist(
        key="case_tracker",
        label="工单进度专员",
        responsibility="只查询当前用户自己的售后工单状态。",
        tool_names=("list_my_after_sales_cases",),
    ),
    "workflow_specialist": Specialist(
        key="workflow_specialist",
        label="售后流程专员",
        responsibility="只创建确认申请或受控工单，绝不直接退款、审核或修改支付状态。",
        tool_names=("prepare_after_sales_confirmation", "create_after_sales_case"),
    ),
}


@dataclass(frozen=True)
class CollaborationPlan:
    """A bounded, explainable team assignment for one customer turn."""

    specialists: tuple[Specialist, ...]

    @property
    def role_keys(self) -> frozenset[str]:
        return frozenset(specialist.key for specialist in self.specialists)

    @property
    def tool_names(self) -> frozenset[str]:
        return frozenset(
            tool_name for specialist in self.specialists for tool_name in specialist.tool_names
        )

    def as_payload(self) -> list[dict[str, str]]:
        return [
            {
                "key": specialist.key,
                "label": specialist.label,
                "responsibility": specialist.responsibility,
            }
            for specialist in self.specialists
        ]

    def as_instruction(self) -> str:
        assignments = "\n".join(
            f"- {specialist.label}：{specialist.responsibility}"
            for specialist in self.specialists
        )
        return (
            "\n\n本轮协作计划由后端固定：\n"
            f"{assignments}\n"
            "你是总控，只能协调上述专员对应的已暴露工具。"
            "最终回复必须汇总已核验的事实；不能声称专员执行了未发生的操作。"
        )


def build_collaboration_plan(message: str) -> CollaborationPlan:
    """Route by business intent without delegating permission decisions to the model."""

    normalized = message.lower()
    role_keys: list[str] = []

    def add_role(key: str) -> None:
        if key not in role_keys:
            role_keys.append(key)

    refund_terms = ("退款", "退钱", "退货", "退回", "取消订单", "不想要")
    order_terms = ("订单", "下单", "购买", "商品", "发货", "物流", "快递", "支付")
    case_terms = ("工单", "审核", "进度", "处理到哪", "处理结果")
    workflow_terms = (
        "退款",
        "退钱",
        "退货",
        "退回",
        "取消",
        "破损",
        "瑕疵",
        "错发",
        "质量",
        "物流异常",
        "没收到",
        "人工",
        "客服",
        "投诉",
    )

    if any(term in normalized for term in case_terms):
        add_role("case_tracker")
    if any(term in normalized for term in order_terms) or any(
        term in normalized for term in refund_terms
    ):
        add_role("order_analyst")
    if any(term in normalized for term in refund_terms) or any(
        term in normalized for term in workflow_terms
    ):
        add_role("policy_advisor")
        add_role("workflow_specialist")
    if any(term in normalized for term in ("规则", "能不能", "可以吗", "售后")):
        add_role("policy_advisor")

    if not role_keys:
        add_role("policy_advisor")

    return CollaborationPlan(tuple(SPECIALISTS[key] for key in role_keys))


def get_stored_plan_payload(context: object) -> list[dict[str, str]]:
    """Read a previously persisted plan defensively for the customer API."""

    if not isinstance(context, dict):
        return []
    raw_plan = context.get("collaboration_plan")
    if not isinstance(raw_plan, list):
        return []

    payload = []
    for item in raw_plan:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        specialist = SPECIALISTS.get(key)
        if specialist:
            payload.append(
                {
                    "key": specialist.key,
                    "label": specialist.label,
                    "responsibility": specialist.responsibility,
                }
            )
    return payload
