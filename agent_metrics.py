
"""Calculate agent observability metrics from audit records."""


def calculate_metrics(records: list[dict]) -> dict:
    """Summarize completed agent requests."""

    total = len(records)

    completed = sum(
        record.get("status") == "COMPLETED"
        for record in records
    )

    blocked = sum(
        record.get("status") in ("BLOCKED", "ACTION_REQUIRED")
        for record in records
    )

    failed = sum(
        record.get("status") == "ERROR"
        for record in records
    )

    tool_executions = sum(
        event.get("event_type") == "TOOL_EXECUTION"
        and event.get("status") == "COMPLETED"
        for record in records
        for event in record.get("audit", {}).get("events", [])
    )

    durations = [
        record["audit"]["duration_ms"]
        for record in records
        if isinstance(record.get("audit", {}).get("duration_ms"),
                      (int, float))
    ]

    average_latency = (
        round(sum(durations) / len(durations), 2)
        if durations else 0
    )

    return {
        "total_requests": total,
        "completed_requests": completed,
        "blocked_requests": blocked,
        "failed_requests": failed,
        "tool_executions": tool_executions,
        "average_latency_ms": average_latency,
    }
