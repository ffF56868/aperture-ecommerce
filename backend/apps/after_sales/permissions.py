"""Runtime permission levels for registered after-sales tools."""

from dataclasses import dataclass
from typing import Any

from .models import AgentConversation, ToolExecution


class ToolPermissionLevel:
    """Risk tiers used by the Agent tool permission matrix."""

    READ_ONLY = "READ_ONLY"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    GUARDED_CASE = "GUARDED_CASE"


ALL_TOOL_PERMISSION_LEVELS = frozenset(
    {
        ToolPermissionLevel.READ_ONLY,
        ToolPermissionLevel.CONFIRMATION_REQUIRED,
        ToolPermissionLevel.GUARDED_CASE,
    }
)


@dataclass(frozen=True)
class ToolPermissionDecision:
    allowed: bool
    code: str = ""
    message: str = ""


def allowed_permission_levels_for_conversation(
    conversation: AgentConversation | None,
) -> frozenset[str]:
    """Do not let a pending customer confirmation compete with a new write action."""

    if conversation and conversation.state == AgentConversation.State.AWAITING_CONFIRMATION:
        return frozenset({ToolPermissionLevel.READ_ONLY})
    return ALL_TOOL_PERMISSION_LEVELS


def authorize_tool(
    *,
    conversation: AgentConversation | None,
    tool: Any,
    allowed_action_kinds: frozenset[str],
    allowed_agent_roles: frozenset[str],
    allowed_permission_levels: frozenset[str],
) -> ToolPermissionDecision:
    """Apply action, specialist and workflow-state gates before a tool runs."""

    if tool.agent_role not in allowed_agent_roles:
        return ToolPermissionDecision(
            False,
            "AGENT_ROLE_DENIED",
            "当前协作计划没有为该专员分配此工具。",
        )
    if tool.action_kind not in allowed_action_kinds:
        return ToolPermissionDecision(
            False,
            "TOOL_PERMISSION_DENIED",
            "当前会话没有执行该工具的权限。",
        )
    if (
        conversation
        and conversation.state == AgentConversation.State.AWAITING_CONFIRMATION
        and tool.permission_level != ToolPermissionLevel.READ_ONLY
    ):
        return ToolPermissionDecision(
            False,
            "CONFIRMATION_PENDING",
            "当前有待你确认的售后申请，请先确认或取消后再发起新的售后操作。",
        )
    if tool.permission_level not in allowed_permission_levels:
        return ToolPermissionDecision(
            False,
            "TOOL_PERMISSION_LEVEL_DENIED",
            "当前会话的权限等级不足，不能执行该工具。",
        )
    return ToolPermissionDecision(True)


def tool_permission_matrix(tools: tuple[Any, ...]) -> list[dict[str, str]]:
    """Return a machine-readable permission summary for documentation and tests."""

    return [
        {
            "tool_name": tool.name,
            "agent_role": tool.agent_role,
            "action_kind": tool.action_kind,
            "permission_level": tool.permission_level,
        }
        for tool in tools
    ]
