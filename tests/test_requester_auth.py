
import unittest

from requester_auth import RequesterAuth


class RequesterAuthTests(unittest.TestCase):

    def setUp(self):
        self.auth = RequesterAuth(
            requester_id="test-agent",
            api_key="test-secret",
            allowed_customers=["CUST-1001"],
        )

    def test_valid_credentials(self):
        self.assertEqual(
            self.auth.authenticate("test-secret"),
            "test-agent",
        )

    def test_invalid_credentials_rejected(self):
        self.assertIsNone(
            self.auth.authenticate("wrong-secret")
        )
        self.assertIsNone(
            self.auth.authenticate(None)
        )

    def test_authorized_customer(self):
        self.assertTrue(
            self.auth.authorize(
                "test-agent",
                "lookup_customer",
                {"customer_id": "CUST-1001"},
            )
        )

    def test_unauthorized_customer_blocked(self):
        self.assertFalse(
            self.auth.authorize(
                "test-agent",
                "lookup_customer",
                {"customer_id": "CUST-9999"},
            )
        )

    def test_unknown_requester_blocked(self):
        self.assertFalse(
            self.auth.authorize(
                "unknown-agent",
                "lookup_customer",
                {"customer_id": "CUST-1001"},
            )
        )

    def test_unknown_tool_blocked(self):
        self.assertFalse(
            self.auth.authorize(
                "test-agent",
                "delete_database",
                {},
            )
        )

    def test_document_search_allowed(self):
        self.assertTrue(
            self.auth.authorize(
                "test-agent",
                "search_documents",
                {"query": "product overview"},
            )
        )


if __name__ == "__main__":
    unittest.main()
