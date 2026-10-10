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
    
    def test_customer_id_routes_private(self):
        decision = inspect("Review customer ID CUST-88021")
        self.assertEqual(decision.route, "PRIVATE")
        self.assertIn("CUSTOMER_ID", decision.signals)

    def test_public_merger_question_is_allowed(self):
        decision = inspect("Explain what a merger is")
        self.assertEqual(decision.route, "CLOUD")
        self.assertEqual(decision.policy_id, "PUBLIC-001")

    def test_unpublished_financial_data_routes_private(self):
        decision = inspect("Summarize unpublished sales forecasts")
        self.assertEqual(decision.route, "PRIVATE")
        self.assertIn("UNPUBLISHED_FORECAST", decision.signals)



if __name__ == "__main__":
    unittest.main()
