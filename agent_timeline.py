
"""Build explainable execution timelines from agent results."""

from policy_engine import inspect


def build_timeline(prompt: str, result: dict) -> list[dict]:
    """Describe verified stages of one agent request."""

    decision = inspect(prompt)

    timeline = [{
        "stage": "Prompt inspection",
        "status": decision.route,
        "detail": decision.reason,
    }]

    if decision.route != "CLOUD":
        timeline.append({
            "stage": "Hosted inference",
            "status": "BLOCKED",
            "detail": "Private requests are not sent to NVIDIA.",
        })
        return timeline

    if result.get("status") == "ERROR":
        timeline.append({
            "stage": "Model interaction",
            "status": "ERROR",
            "detail": result.get("reason", "Model request failed"),
        })
        return timeline

    timeline.append({
        "stage": "Model interaction",
        "status": "REQUESTED",
        "detail": "Request eligible for hosted inference.",
    })

    for tool in result.get("tools", []):
        timeline.append({
            "stage": "Tool requested",
            "status": "PROPOSED",
            "detail": tool["tool"],
        })

        status = tool["status"]

        timeline.append({
            "stage": "Tool enforcement",
            "status": status,
            "detail": tool.get("reason", ""),
        })

    if result.get("status") == "COMPLETED":
        timeline.append({
            "stage": "Final response",
            "status": "COMPLETED",
            "detail": "Nemotron returned a final answer.",
        })
    else:
        timeline.append({
            "stage": "Agent outcome",
            "status": result.get("status", "UNKNOWN"),
            "detail": result.get("reason", "Execution stopped."),
        })

    return timeline
