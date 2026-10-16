
"""NVIDIA Nemotron agent with AgentGate policy enforcement."""

import json
import os

from openai import OpenAI

from agent_schemas import TOOL_SCHEMAS
from policy_engine import inspect
from tool_gateway import run_tool
from agent_audit import AgentAudit

from dotenv import load_dotenv

load_dotenv()


MODEL = "nvidia/nemotron-3-super-120b-a12b"


def run_agent(
    prompt: str,
    client=None,
    tool_runner=None,
    trusted_customer_id=None,
) -> dict:
    """Perform one policy-governed Nemotron interaction."""

    audit = AgentAudit()

    def finish(result: dict) -> dict:
        """Attach audit information to the final result."""
        audit.record(
            "AGENT_OUTCOME",
            result.get("status", "UNKNOWN"),
        )
        result["audit"] = audit.summary()
        return result

    if not isinstance(prompt, str) or not prompt.strip():
        return finish({
            "status": "BLOCKED",
            "reason": "Prompt must be a non-empty string",
        })

    decision = inspect(prompt)

    audit.record(
        "PROMPT_INSPECTION",
        decision.route,
        decision.policy_id,
    )

    # Private prompts never reach hosted NVIDIA inference.
    if decision.route != "CLOUD":
        return finish({
            "status": "BLOCKED",
            "reason": "Private requests cannot use hosted Nemotron",
            "policy_id": decision.policy_id,
        })

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
                "You may request tools when necessary. "
                "Use search_documents for public document questions. "
                "Use short, relevant search queries. "
                "If a tool returns no matching documents, explain that "
                "no matching information was found rather than requesting "
                "another tool call. "
                "For customer record lookup requests, the trusted backend "
                "already holds the customer identifier. Never ask the user "
                "to provide it in chat. Use lookup_customer with customer_id "
                "set to exactly TRUSTED_CUSTOMER. "
                "The gateway resolves that placeholder locally and requires "
                "human approval before executing the lookup. "
                "Never claim an action ran unless its result confirms "
                "completion. You cannot approve your own tool calls."


            ),
        },
        {"role": "user", "content": prompt},
    ]


    audit.record(
        "MODEL_REQUEST",
        "STARTED",
        "Hosted Nemotron inference",
    )

    try:
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
    except Exception:
        audit.record(
            "MODEL_REQUEST",
            "ERROR",
            "Hosted inference failed",
        )
        return finish({
            "status": "ERROR",
            "reason": "Hosted model request failed",
            "tools": [],
        })

    audit.record(
        "MODEL_RESPONSE",
        "RECEIVED",
        "Hosted Nemotron response",
    )

    message = response.choices[0].message
    calls = message.tool_calls or []


    if not calls:
        return finish({
            "status": "COMPLETED",
            "answer": message.content or "",
            "tools": [],
        })

    results = []

    # Model-generated arguments cannot authorize execution.
    for call in calls:
        tool_name = call.function.name

        try:
            arguments = json.loads(call.function.arguments)

        except (ValueError, TypeError):
            audit.record(
                "TOOL_POLICY",
                "BLOCKED",
                "Invalid JSON arguments",
            )

            results.append({
                "tool": tool_name,
                "status": "BLOCKED",
                "reason": "Invalid JSON arguments",
            })
            continue
        # Customer identities must come from trusted server context.
        if tool_name == "lookup_customer":
            valid_context = (
                isinstance(trusted_customer_id, str)
                and bool(trusted_customer_id.strip())
            )

            valid_proposal = (
                arguments == {"customer_id": "TRUSTED_CUSTOMER"}
            )

            if not valid_context or not valid_proposal:
                audit.record(
                    "TOOL_POLICY",
                    "BLOCKED",
                    "Customer lookup requires trusted context",
                )
                results.append({
                    "tool": tool_name,
                    "status": "BLOCKED",
                    "reason": "Customer lookup requires trusted context",
                })
                continue

            # The model never chooses the real customer identifier.
            arguments = {"customer_id": trusted_customer_id}

        # All tool calls must still pass through the policy gateway.
        gateway = tool_runner if tool_runner is not None else run_tool
        tool_result = gateway(tool_name, arguments)

        # Record the gateway's returned decision.
        audit.record(
            "TOOL_POLICY",
            tool_result["status"],
            tool_name,
        )

        # Only record execution when the tool completed.
        if tool_result["status"] == "COMPLETED":
            audit.record(
                "TOOL_EXECUTION",
                "COMPLETED",
                tool_name,
            )

        results.append({
            "tool": tool_name,
            **tool_result,
        })

    # Stop if any call is restricted, failed, or awaiting approval.
    # Nothing from these results is sent back to NVIDIA.
    if any(item["status"] != "COMPLETED" for item in results):
        return finish({
            "status": "ACTION_REQUIRED",
            "answer": "",
            "tools": results,
        })

    # Only explicitly public document-search results may be
    # returned to NVIDIA's hosted inference endpoint.
    safe_results = []

    for item in results:
        if item["tool"] != "search_documents":
            return finish({
                "status": "BLOCKED",
                "answer": "",
                "reason": "Tool output not approved for hosted inference",
                "tools": [],
            })


        documents = item["result"].get("results", [])

        if not isinstance(documents, list):
            return finish({
                "status": "BLOCKED",
                "reason": "Unexpected tool output",
                "tools": [],
            })

        for document in documents:
            if (
                not isinstance(document, dict)
                or document.get("classification") != "PUBLIC"
            ):
                return finish({
                    "status": "BLOCKED",
                    "reason": "Restricted document output",
                    "tools": [],
                })

        safe_results.append(item["result"])

    # Preserve the model's tool-call IDs when sending results.
    messages.append(message.model_dump() if hasattr(
        message, "model_dump"
    ) else {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in calls
        ],
    })

    for call, tool_result in zip(calls, safe_results):
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(tool_result),
        })


    audit.record(
        "MODEL_REQUEST",
        "STARTED",
        "Hosted final response",
    )

    try:
        final_response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tool_choice="none",
            temperature=1.0,
            top_p=0.95,
            max_tokens=1024,
            stream=False,
        )
    except Exception:
        audit.record(
            "MODEL_REQUEST",
            "ERROR",
            "Hosted final response failed",
        )
        return finish({
            "status": "ERROR",
            "reason": "Final model request failed",
            "tools": results,
        })

    audit.record(
        "MODEL_RESPONSE",
        "RECEIVED",
        "Hosted final response",
    )

    final_message = final_response.choices[0].message

    # Never execute additional tool calls in this prototype.
    if final_message.tool_calls:
        return finish({
            "status": "BLOCKED",
            "reason": "Additional tool rounds are disabled",
            "tools": results,
        })


    return finish({
        "status": "COMPLETED",
        "answer": final_message.content or "",
        "tools": results,
    })
