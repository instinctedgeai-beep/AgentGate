
"""Tests for Nemotron agent policy enforcement."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from nemotron_agent import run_agent


def fake_client(tool_calls=None, content=""):
    """Simulate NVIDIA responses without API calls."""

    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls or [],
    )

    client = Mock()
    client.chat.completions.create.return_value = (
        SimpleNamespace(
            choices=[SimpleNamespace(message=message)]
        )
    )

    return client



def fake_tool(name, arguments, call_id="call_test_001"):
    """Create a realistic mock Nemotron tool call."""

    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments),
        ),
    )


class NemotronAgentTests(unittest.TestCase):

    def test_private_prompt_never_reaches_nvidia(self):
        client = fake_client()

        result = run_agent(
            "My email is alex@example.com",
            client=client,
        )

        self.assertEqual(result["status"], "BLOCKED")
        client.chat.completions.create.assert_not_called()

    def test_public_prompt_reaches_model(self):
        client = fake_client(content="Hello from Nemotron")

        result = run_agent(
            "Explain what AgentGate does.",
            client=client,
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(
            result["answer"], "Hello from Nemotron"
        )
        client.chat.completions.create.assert_called_once()


    def test_public_document_search_executes(self):
        client = fake_client([
            fake_tool(
                "search_documents",
                {"query": "product"},
            )
        ])

        first_response = (
            client.chat.completions.create.return_value
        )

        final_message = SimpleNamespace(
            content="AgentGate monitors AI routing and policy decisions.",
            tool_calls=[],
        )

        final_response = SimpleNamespace(
            choices=[
                SimpleNamespace(message=final_message)
            ]
        )

        client.chat.completions.create.side_effect = [
            first_response,
            final_response,
        ]

        result = run_agent(
            "Find the public product overview.",
            client=client,
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(
            result["tools"][0]["status"],
            "COMPLETED",
        )
        self.assertIn("AgentGate", result["answer"])
        self.assertEqual(
            client.chat.completions.create.call_count,
            2,
        )


    def test_customer_lookup_requires_approval(self):
        client = fake_client([
            fake_tool(
                "lookup_customer",
                {"customer_id": "CUST-1001"},
            )
        ])

        result = run_agent(
            "Look up a fictional customer.",
            client=client,
        )

        self.assertEqual(
            result["tools"][0]["status"],
            "APPROVAL_REQUIRED",
        )

    def test_unknown_tool_is_blocked(self):
        client = fake_client([
            fake_tool("delete_database", {})
        ])

        result = run_agent(
            "Run an administrative operation.",
            client=client,
        )

        self.assertEqual(
            result["tools"][0]["status"], "BLOCKED"
        )

    def test_model_cannot_supply_approval_token(self):
        client = fake_client([
            fake_tool(
                "lookup_customer",
                {
                    "customer_id": "CUST-1001",
                    "approval_id": "fake-approval",
                },
            )
        ])

        result = run_agent(
            "Find a fictional customer record.",
            client=client,
        )

        self.assertEqual(
            result["tools"][0]["status"], "BLOCKED"
        )


    def test_document_search_generates_final_answer(self):
        first_message = SimpleNamespace(
            content=None,
            tool_calls=[
                SimpleNamespace(
                    id="call_123",
                    type="function",
                    function=SimpleNamespace(
                        name="search_documents",
                        arguments=json.dumps({"query": "product"}),
                    ),
                )
            ],
        )

        final_message = SimpleNamespace(
            content="AgentGate monitors AI routing and policy decisions.",
            tool_calls=[],
        )

        client = Mock()
        client.chat.completions.create.side_effect = [
            SimpleNamespace(
                choices=[SimpleNamespace(message=first_message)]
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(message=final_message)]
            ),
        ]

        result = run_agent(
            "Explain the public product overview.",
            client=client,
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertIn("AgentGate", result["answer"])
        self.assertEqual(
            client.chat.completions.create.call_count, 2
        )

    def test_customer_data_never_reaches_second_model_call(self):
        client = fake_client([
            fake_tool(
                "lookup_customer",
                {"customer_id": "CUST-1001"},
            )
        ])

        result = run_agent(
            "Look up a fictional customer.",
            client=client,
        )

        self.assertEqual(result["status"], "ACTION_REQUIRED")
        client.chat.completions.create.assert_called_once()


    def test_restricted_tool_output_never_reaches_nvidia(self):
        client = fake_client([
            fake_tool(
                "search_documents",
                {"query": "product"},
            )
        ])

        restricted_result = {
            "status": "COMPLETED",
            "reason": "Public document search permitted",
            "result": {
                "results": [{
                    "id": "finance",
                    "title": "Financial Forecast",
                    "content": "Synthetic secret forecast",
                    "classification": "CONFIDENTIAL",
                }]
            },
        }

        with patch(
            "nemotron_agent.run_tool",
            return_value=restricted_result,
        ):
            result = run_agent(
                "Find the public product overview.",
                client=client,
            )

        self.assertEqual(result["status"], "BLOCKED")

        # Confidential tool data must not trigger
        # a second hosted model request.
        client.chat.completions.create.assert_called_once()
        
if __name__ == "__main__":
    unittest.main()
