
"""Tests for Nemotron agent policy enforcement."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

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


def fake_tool(name, arguments):
    return SimpleNamespace(
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments),
        )
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
            fake_tool("search_documents", {"query": "product"})
        ])

        result = run_agent(
            "Find the public product overview.",
            client=client,
        )

        self.assertEqual(
            result["tools"][0]["status"], "COMPLETED"
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


if __name__ == "__main__":
    unittest.main()
