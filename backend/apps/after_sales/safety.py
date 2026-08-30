"""Safety checks for model-originated tool calls before any business execution."""

import re
from dataclasses import dataclass
from typing import Any, Mapping


_DANGEROUS_NAME_FRAGMENTS = (
    "sql",
    "database",
    "shell",
    "command",
    "subprocess",
    "terminal",
    "powershell",
    "bash",
    "cmd",
    "exec",
    "filesystem",
    "file",
    "http",
    "fetch",
    "webhook",
    "browser",
    "curl",
    "payment",
    "transfer",
    "withdraw",
)
_DANGEROUS_DIRECT_ACTIONS = {
    "refund",
    "direct_refund",
    "refund_order",
    "cancel_order",
    "approve_case",
    "reject_case",
    "update_order",
    "set_order_status",
    "delete_order",
}
_DANGEROUS_ARGUMENT_KEY_FRAGMENTS = (
    "sql",
    "query",
    "command",
    "script",
    "shell",
    "path",
    "file",
    "url",
    "uri",
    "endpoint",
    "webhook",
    "authorization",
    "token",
    "secret",
    "api_key",
    "password",
)


@dataclass(frozen=True)
class ToolSafetyDecision:
    """An intentionally small, log-safe result of safety inspection."""

    blocked: bool
    code: str = ""
    message: str = ""
    matched_keys: tuple[str, ...] = ()


def _normalize_identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def inspect_tool_name(tool_name: str) -> ToolSafetyDecision:
    """Reject dangerous capabilities even though they are never registered as tools."""

    normalized = _normalize_identifier(tool_name)
    collapsed = normalized.replace("_", "")
    if normalized in _DANGEROUS_DIRECT_ACTIONS or any(
        fragment in collapsed for fragment in _DANGEROUS_NAME_FRAGMENTS
    ):
        return ToolSafetyDecision(
            True,
            "DANGEROUS_TOOL_CALL_BLOCKED",
            "已拦截与售后无关或可能修改系统数据的危险工具调用。",
        )
    return ToolSafetyDecision(False)


def _collect_dangerous_argument_keys(value: Any, *, depth: int = 0) -> set[str]:
    if depth > 4:
        return set()
    if isinstance(value, Mapping):
        matched = set()
        for key, nested_value in value.items():
            normalized_key = _normalize_identifier(str(key))
            collapsed_key = normalized_key.replace("_", "")
            if any(fragment.replace("_", "") in collapsed_key for fragment in _DANGEROUS_ARGUMENT_KEY_FRAGMENTS):
                matched.add(normalized_key or "unknown")
            matched.update(_collect_dangerous_argument_keys(nested_value, depth=depth + 1))
        return matched
    if isinstance(value, (list, tuple)):
        matched = set()
        for item in value:
            matched.update(_collect_dangerous_argument_keys(item, depth=depth + 1))
        return matched
    return set()


def inspect_tool_arguments(arguments: Any) -> ToolSafetyDecision:
    """Reject executable or credential-bearing argument shapes without inspecting text values."""

    matched_keys = tuple(sorted(_collect_dangerous_argument_keys(arguments)))
    if matched_keys:
        return ToolSafetyDecision(
            True,
            "DANGEROUS_ARGUMENT_BLOCKED",
            "已拦截包含危险系统参数的工具调用。",
            matched_keys,
        )
    return ToolSafetyDecision(False)


def is_security_rejection(result: Any) -> bool:
    """Identify safe, intentional rejections that must stop the Agent tool loop."""

    if not isinstance(result, Mapping):
        return False
    error = result.get("error")
    if not isinstance(error, Mapping):
        return False
    return error.get("code") in {
        "DANGEROUS_TOOL_CALL_BLOCKED",
        "DANGEROUS_ARGUMENT_BLOCKED",
    }


def security_audit_arguments(arguments: Any, decision: ToolSafetyDecision) -> dict[str, Any]:
    """Keep only non-sensitive evidence for a blocked tool call audit."""

    payload: dict[str, Any] = {"blocked": True}
    if decision.matched_keys:
        payload["blocked_argument_keys"] = list(decision.matched_keys)
    elif isinstance(arguments, Mapping):
        payload["argument_keys"] = sorted(str(key)[:100] for key in arguments.keys())[:20]
    return payload
