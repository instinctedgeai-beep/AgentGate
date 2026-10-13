
import unittest

from agent_metrics import calculate_metrics


class AgentMetricsTests(unittest.TestCase):

    def test_empty_records(self):
        metrics = calculate_metrics([])

        self.assertEqual(metrics["total_requests"], 0)
        self.assertEqual(metrics["tool_executions"], 0)
        self.assertEqual(metrics["average_latency_ms"], 0)

    def test_metrics_from_multiple_requests(self):
        records = [
            {
                "status": "COMPLETED",
                "audit": {
                    "duration_ms": 100,
                    "events": [{
                        "event_type": "TOOL_EXECUTION",
                        "status": "COMPLETED",
                    }],
                },
            },
            {
                "status": "BLOCKED",
                "audit": {
                    "duration_ms": 20,
                    "events": [],
                },
            },
            {
                "status": "ERROR",
                "audit": {
                    "duration_ms": 30,
                    "events": [],
                },
            },
        ]

        metrics = calculate_metrics(records)

        self.assertEqual(metrics["total_requests"], 3)
        self.assertEqual(metrics["completed_requests"], 1)
        self.assertEqual(metrics["blocked_requests"], 1)
        self.assertEqual(metrics["failed_requests"], 1)
        self.assertEqual(metrics["tool_executions"], 1)
        self.assertEqual(metrics["average_latency_ms"], 50)


if __name__ == "__main__":
    unittest.main()
