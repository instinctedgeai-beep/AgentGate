
import unittest
from unittest.mock import patch
from approval_manager import ApprovalManager
from tool_gateway import run_tool


class ToolGatewayTests(unittest.TestCase):

    def test_public_search_allowed(self):
        result = run_tool(
            "search_documents",
            {"query": "product"},
        )
        self.assertEqual(result["status"], "COMPLETED")

    def test_customer_lookup_requires_approval(self):
        with patch("tool_gateway.lookup_customer") as lookup:
            result = run_tool(
                "lookup_customer",
                {"customer_id": "CUST-1001"},
            )
            self.assertEqual(
                result["status"], "APPROVAL_REQUIRED"
            )
            lookup.assert_not_called()

    def test_external_email_blocked(self):
        result = run_tool(
            "draft_email",
            {
                "recipient": "outside@gmail.com",
                "subject": "Hello",
                "body": "Test message",
            },
        )
        self.assertEqual(result["status"], "BLOCKED")

    def test_unknown_tool_blocked(self):
        result = run_tool("delete_database", {})
        self.assertEqual(result["status"], "BLOCKED")

    def test_invalid_arguments_blocked(self):
        result = run_tool(
            "search_documents",
            {"query": "product", "admin": "true"},
        )
        self.assertEqual(result["status"], "BLOCKED")


    def test_public_document_content_visible(self):
        result = run_tool(
            "search_documents",
            {"query": "product"},
        )

        self.assertEqual(result["status"], "COMPLETED")
        documents = result["result"]["results"]

        self.assertTrue(
            any(doc["classification"] == "PUBLIC"
                for doc in documents)
        )

    def test_confidential_document_content_hidden(self):
        result = run_tool(
            "search_documents",
            {"query": "revenue"},
        )

        self.assertEqual(result["status"], "COMPLETED")

        documents = result["result"]["results"]
        self.assertTrue(
            any(doc.get("status") == "ACCESS_DENIED"
                for doc in documents)
        )

        self.assertNotIn(
            "$2.4M",
            str(documents),
        )

    
    def test_approved_customer_lookup_executes_once(self):
        manager = ApprovalManager()
        args = {"customer_id": "CUST-1001"}

        request = manager.create_request("lookup_customer", args)
        manager.approve(request.approval_id)

        first = run_tool(
            "lookup_customer", args,
            approval_id=request.approval_id,
            approval_manager=manager,
        )

        second = run_tool(
            "lookup_customer", args,
            approval_id=request.approval_id,
            approval_manager=manager,
        )

        self.assertEqual(first["status"], "COMPLETED")
        self.assertEqual(second["status"], "APPROVAL_REQUIRED")

    def test_rejected_approval_cannot_execute(self):
        manager = ApprovalManager()
        args = {"customer_id": "CUST-1001"}

        request = manager.create_request("lookup_customer", args)
        manager.reject(request.approval_id)

        result = run_tool(
            "lookup_customer", args,
            approval_id=request.approval_id,
            approval_manager=manager,
        )

        self.assertEqual(result["status"], "APPROVAL_REQUIRED")

    def test_modified_arguments_cannot_execute(self):
        manager = ApprovalManager()

        request = manager.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )
        manager.approve(request.approval_id)

        result = run_tool(
            "lookup_customer",
            {"customer_id": "CUST-9999"},
            approval_id=request.approval_id,
            approval_manager=manager,
        )

        self.assertEqual(result["status"], "APPROVAL_REQUIRED")


if __name__ == "__main__":
    unittest.main()
