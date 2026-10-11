
import unittest

from approval_manager import ApprovalManager


class ApprovalTests(unittest.TestCase):

    def setUp(self):
        self.manager = ApprovalManager()
        self.request = self.manager.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

    def test_request_starts_pending(self):
        self.assertEqual(self.request.status, "PENDING")

    def test_approval_changes_status(self):
        self.assertTrue(
            self.manager.approve(self.request.approval_id)
        )
        self.assertEqual(self.request.status, "APPROVED")

    def test_rejection_changes_status(self):
        self.assertTrue(
            self.manager.reject(self.request.approval_id)
        )
        self.assertEqual(self.request.status, "REJECTED")

    def test_cannot_approve_twice(self):
        self.manager.approve(self.request.approval_id)
        self.assertFalse(
            self.manager.approve(self.request.approval_id)
        )

    def test_invalid_approval_id(self):
        self.assertFalse(
            self.manager.approve("invalid-id")
        )


if __name__ == "__main__":
    unittest.main()
