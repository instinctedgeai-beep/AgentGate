
import unittest

from agent_audit import AgentAudit


class AgentAuditTests(unittest.TestCase):

    def test_new_audit_has_unique_request_id(self):
        first = AgentAudit()
        second = AgentAudit()

        self.assertNotEqual(
            first.request_id,
            second.request_id,
        )

    def test_event_recording(self):
        audit = AgentAudit()

        audit.record(
            "TOOL_POLICY",
            "ALLOW",
            "Public document search permitted",
        )

        result = audit.summary()

        self.assertEqual(result["event_count"], 1)
        self.assertEqual(
            result["events"][0]["status"],
            "ALLOW",
        )

    def test_duration_is_nonnegative(self):
        audit = AgentAudit()

        self.assertGreaterEqual(
            audit.summary()["duration_ms"],
            0,
        )

    def test_events_share_request_id(self):
        audit = AgentAudit()

        first = audit.record("PROMPT_INSPECTION", "CLOUD")
        second = audit.record("TOOL_EXECUTION", "COMPLETED")

        self.assertEqual(
            first.request_id,
            second.request_id,
        )


if __name__ == "__main__":
    unittest.main()
