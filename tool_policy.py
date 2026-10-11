
"""Deterministic authorization for AgentGate agent tools."""

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ToolDecision:
    action: str
    reason: str


ALLOWED_TOOLS = {
    "search_documents",
    "lookup_customer",
    "draft_email",
}


def check_tool_policy(
    tool_name: str,
    arguments: dict,
) -> ToolDecision:
    """Return ALLOW, BLOCK, or APPROVAL_REQUIRED."""

    if tool_name not in ALLOWED_TOOLS:
        return ToolDecision("BLOCK", "Unknown tool")

    if tool_name == "lookup_customer":
        return ToolDecision(
            "APPROVAL_REQUIRED",
            "Customer records require human approval",
        )

    if tool_name == "search_documents":
        query = arguments.get("query", "").lower()
        if "finance" in query or "forecast" in query:
            return ToolDecision(
                "APPROVAL_REQUIRED",
                "Confidential documents require approval",
            )
        return ToolDecision("ALLOW", "Public document search permitted")

    if tool_name == "draft_email":
        recipient = arguments.get("recipient", "").lower()

        if not recipient.endswith("@company.test"):
            return ToolDecision(
                "BLOCK",
                "External email destinations are restricted",
            )

        return ToolDecision(
            "APPROVAL_REQUIRED",
            "Email drafts require review",
        )

    return ToolDecision("BLOCK", "No matching permission rule")
