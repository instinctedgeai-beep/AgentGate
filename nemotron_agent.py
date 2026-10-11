
"""NVIDIA Nemotron agent with AgentGate policy enforcement."""

import json
import os

from openai import OpenAI

from agent_schemas import TOOL_SCHEMAS
from policy_engine import inspect
from tool_gateway import run_tool

from dotenv import load_dotenv

load_dotenv()


MODEL = "nvidia/nemotron-3-super-120b-a12b"


def run_agent(prompt: str, client=None) -> dict:
    """Perform one policy-governed Nemotron interaction."""

    if not isinstance(prompt, str) or not prompt.strip():
        return {
            "status": "BLOCKED",
            "reason": "Prompt must be a non-empty string",
        }

    decision = inspect(prompt)

    # Private prompts never reach hosted NVIDIA inference.
    if decision.route != "CLOUD":
        return {
            "status": "BLOCKED",
            "reason": "Private requests cannot use hosted Nemotron",
            "policy_id": decision.policy_id,
        }

    if client is None:
        api_key = os.getenv("NVIDIA_API_KEY")

        if not api_key:
            return {
                "status": "ERROR",
                "reason": "NVIDIA_API_KEY is not configured",
            }

        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            timeout=30.0,
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are the AgentGate enterprise assistant. "
                "Use tools when helpful. Never claim a tool "
                "ran unless its result confirms completion. "
                "You cannot approve your own tool calls."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOL_SCHEMAS,
        tool_choice="auto",
        temperature=1.0,
        top_p=0.95,
        max_tokens=1024,
        stream=False,
    )

    message = response.choices[0].message
    calls = message.tool_calls or []

    if not calls:
        return {
            "status": "COMPLETED",
            "answer": message.content or "",
            "tools": [],
        }

    results = []

    # Model-generated arguments cannot authorize execution.
    for call in calls:
        tool_name = call.function.name

        try:
            arguments = json.loads(call.function.arguments)
        except (ValueError, TypeError):
            results.append({
                "tool": tool_name,
                "status": "BLOCKED",
                "reason": "Invalid JSON arguments",
            })
            continue

        tool_result = run_tool(tool_name, arguments)

        results.append({
            "tool": tool_name,
            **tool_result,
        })

    return {
        "status": "TOOL_RESULTS",
        "answer": message.content or "",
        "tools": results,
    }
