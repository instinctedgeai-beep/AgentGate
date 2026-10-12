"""Pure data helpers for the AgentGate control room (no Streamlit imports).

Everything here works on the session history the dashboard records, so it can
be unit-tested without a running Streamlit server.
"""

from collections import Counter
from statistics import median

# Synthetic prompts used by "Load demo traffic". They run through the real
# policy engine in simulate mode, so the decisions shown are genuine.
DEMO_PROMPTS = [
    "Explain how NVIDIA GPUs accelerate AI inference.",
    "Draft a public announcement about our new office.",
    "Summarize the record for sample.user@example.com.",
    "Review confidential merger negotiations.",
    "Write a weekly planning template.",
    "Call 404-555-0123 to confirm the order.",
    "Please parse the customer ID CUST-88021.",
    "Brainstorm a team offsite agenda.",
    "Summarize the unreleased quarterly earnings report.",
    "Compare electric and gas cars.",
    "My password: sampleSecret123",
    "Explain SQL joins to a beginner.",
]

SAMPLE_PROMPTS = {
    "Public": "Explain how NVIDIA GPUs accelerate AI inference.",
    "Personal": "Summarize the record for sample.user@example.com.",
    "Confidential": "Review confidential merger negotiations.",
}

# Mirrors tool_policy.check_tool_policy for display purposes only;
# enforcement always goes through tool_gateway.run_tool.
TOOL_POLICY_MATRIX = [
    ("search_documents", "Query mentions finance or forecast", "APPROVAL_REQUIRED"),
    ("search_documents", "Any other query (restricted bodies redacted)", "ALLOW"),
    ("lookup_customer", "Every customer record", "APPROVAL_REQUIRED"),
    ("draft_email", "Recipient outside @company.test", "BLOCK"),
    ("draft_email", "Internal recipient", "APPROVAL_REQUIRED"),
    ("any other tool", "Not on the allow-list", "BLOCK"),
]

TOOL_PRESETS = {
    "Public doc search": ("search_documents", {"query": "product"}),
    "Finance forecast": ("search_documents", {"query": "forecast"}),
    "Customer record": ("lookup_customer", {"customer_id": "CUST-1001"}),
    "External email": (
        "draft_email",
        {
            "recipient": "partner@external.example",
            "subject": "Q3 update",
            "body": "Sharing the latest numbers.",
        },
    ),
}

TOOL_FIELDS = {
    "search_documents": ["query"],
    "lookup_customer": ["customer_id"],
    "draft_email": ["recipient", "subject", "body"],
}


def verdict(item: dict) -> tuple[str, str, str]:
    """Return (tone, headline, explanation) for one recorded decision."""
    route, status = item["route"], item["status"]
    if status == "ERROR":
        return "blocked", "Inference error", "The model call failed after routing."
    if route == "CLOUD":
        if status == "COMPLETED":
            return "cloud", "Answered by hosted Nemotron", "Public prompt, eligible for hosted inference."
        if status == "BLOCKED":
            return "blocked", "Cloud call blocked", "Hosted inference is not configured."
        return "cloud", "Cleared for cloud inference", "No sensitive pattern found. Simulated, no model call made."
    if status == "COMPLETED":
        return "private", "Answered on the private route", "Sensitive prompt handled by the local NIM endpoint."
    if status == "BLOCKED":
        return "blocked", "Held: no private endpoint", "Sensitive prompt. Nothing was transmitted."
    return "private", "Private route required", "Sensitive data detected. Hosted inference is not allowed."


def kpis(history: list, pending_approvals: int = 0) -> dict:
    total = len(history)
    private = sum(r["route"] == "PRIVATE" for r in history)
    blocked = sum(r["status"] == "BLOCKED" for r in history)
    times = [r["inspection_ms"] for r in history if r.get("inspection_ms") is not None]
    return {
        "total": total,
        "cloud": total - private,
        "private": private,
        "private_share": (private / total) if total else None,
        "blocked": blocked,
        "median_ms": median(times) if times else None,
        "pending": pending_approvals,
    }


def route_mix(history: list) -> list[dict]:
    """Rows for the route/outcome donut: Cloud, Private, Blocked."""
    counts = Counter()
    for r in history:
        if r["status"] == "BLOCKED":
            counts["Blocked"] += 1
        elif r["route"] == "PRIVATE":
            counts["Private"] += 1
        else:
            counts["Cloud"] += 1
    return [{"Outcome": k, "Requests": counts[k]} for k in ("Cloud", "Private", "Blocked") if counts[k]]


def signal_counts(history: list) -> list[dict]:
    counts = Counter(s for r in history for s in r.get("signals", []))
    return [{"Signal": k, "Count": v} for k, v in counts.most_common()]


def label_signal(name: str) -> str:
    return name.replace("_", " ").title()
