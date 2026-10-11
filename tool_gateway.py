
"""Enforced execution gateway for approved AgentGate tools."""

from agent_tools import (
    search_documents,
    lookup_customer,
    draft_email,
)
from tool_policy import check_tool_policy
from approval_manager import ApprovalManager


TOOLS = {
    "search_documents": search_documents,
    "lookup_customer": lookup_customer,
    "draft_email": draft_email,
}

ARGUMENTS = {
    "search_documents": {"query"},
    "lookup_customer": {"customer_id"},
    "draft_email": {"recipient", "subject", "body"},
}


def run_tool(
    tool_name: str,
    arguments: dict,
    approval_id=None,
    approval_manager: ApprovalManager = None,
) -> dict:
    """Check permissions before invoking a registered tool."""

    if tool_name not in TOOLS:
        return {
            "status": "BLOCKED",
            "reason": "Unknown tool",
        }

    if not isinstance(arguments, dict):
        return {
            "status": "BLOCKED",
            "reason": "Tool arguments must be an object",
        }

    if set(arguments) != ARGUMENTS[tool_name]:
        return {
            "status": "BLOCKED",
            "reason": "Invalid tool arguments",
        }

    if not all(
        isinstance(value, str) and value.strip()
        for value in arguments.values()
    ):
        return {
            "status": "BLOCKED",
            "reason": "Arguments must be non-empty strings",
        }

    decision = check_tool_policy(tool_name, arguments)


    if decision.action == "BLOCK":
        return {
            "status": "BLOCKED",
            "reason": decision.reason,
        }

    if decision.action == "APPROVAL_REQUIRED":
        if (
            approval_manager is None
            or approval_id is None
            or not approval_manager.consume(
                approval_id, tool_name, arguments
            )
        ):
            return {
                "status": "APPROVAL_REQUIRED",
                "reason": decision.reason,
            }

    elif decision.action != "ALLOW":
        return {
            "status": "BLOCKED",
            "reason": "Unrecognized policy decision",
        }


    try:
        result = TOOLS[tool_name](**arguments)
    except Exception:
        return {
            "status": "ERROR",
            "reason": "Tool execution failed",
        }

    return {
        "status": "COMPLETED",
        "reason": decision.reason,
        "result": result,
    }
