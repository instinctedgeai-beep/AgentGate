"""Small, repeatable regression checks for the existing AgentGate inspector."""
import unittest
from engine import inspect


class RoutingTests(unittest.TestCase):
    def test_benign_request_is_cloud_eligible(self):
        result = inspect("Explain how a GPU works.")
        self.assertEqual(result.route, "CLOUD")

    def test_email_routes_private(self):
        result = inspect("Contact test@example.com about our rollout.")
        self.assertEqual(result.route, "PRIVATE")
        self.assertIn("EMAIL", result.signals)

    def test_confidential_business_information_routes_private(self):
        result = inspect("Review confidential merger negotiations.")
        self.assertEqual(result.route, "PRIVATE")


if __name__ == "__main__":
    unittest.main()
