
import unittest

from agent_timeline import build_timeline


class AgentTimelineTests(unittest.TestCase):

    def test_private_prompt_stops_before_model(self):
        timeline = build_timeline(
            "My email is alex@example.com",
            {"status": "BLOCKED"},
        )

        self.assertEqual(timeline[0]["status"], "PRIVATE")
        self.assertEqual(timeline[1]["status"], "BLOCKED")
        self.assertEqual(len(timeline), 2)

    def test_public_tool_execution_is_visible(self):
        timeline = build_timeline(
            "Find the public product overview.",
            {
                "status": "COMPLETED",
                "answer": "AgentGate monitors AI routing.",
                "tools": [{
                    "tool": "search_documents",
                    "status": "COMPLETED",
                    "reason": "Public document search permitted",
                }],
            },
        )

        stages = [event["stage"] for event in timeline]

        self.assertIn("Tool requested", stages)
        self.assertIn("Tool enforcement", stages)
        self.assertIn("Final response", stages)

    def test_approval_requirement_is_visible(self):
        timeline = build_timeline(
            "Look up a fictional customer.",
            {
                "status": "ACTION_REQUIRED",
                "tools": [{
                    "tool": "lookup_customer",
                    "status": "APPROVAL_REQUIRED",
                    "reason": "Customer records require approval",
                }],
            },
        )

        self.assertTrue(
            any(event["status"] == "APPROVAL_REQUIRED"
                for event in timeline)
        )


if __name__ == "__main__":
    unittest.main()
