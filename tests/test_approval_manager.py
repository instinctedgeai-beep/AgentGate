
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

    def test_approved_request_can_be_consumed(self):
        self.manager.approve(self.request.approval_id)

        self.assertTrue(
            self.manager.consume(
                self.request.approval_id,
                "lookup_customer",
                {"customer_id": "CUST-1001"},
            )
        )
        self.assertEqual(self.request.status, "CONSUMED")

    def test_approval_cannot_be_reused(self):
        self.manager.approve(self.request.approval_id)

        self.manager.consume(
            self.request.approval_id,
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        self.assertFalse(
            self.manager.consume(
                self.request.approval_id,
                "lookup_customer",
                {"customer_id": "CUST-1001"},
            )
        )

    def test_approval_rejects_changed_arguments(self):
        self.manager.approve(self.request.approval_id)

        self.assertFalse(
            self.manager.consume(
                self.request.approval_id,
                "lookup_customer",
                {"customer_id": "CUST-9999"},
            )
        )

    def test_approval_records_reviewer(self):
        self.assertTrue(
            self.manager.approve(
                self.request.approval_id,
                reviewer_id="reviewer-01",
            )
        )
        self.assertEqual(self.request.reviewed_by, "reviewer-01")
        self.assertIsNotNone(self.request.reviewed_at)

    def test_rejection_records_reviewer(self):
        self.assertTrue(
            self.manager.reject(
                self.request.approval_id,
                reviewer_id="reviewer-02",
            )
        )
        self.assertEqual(self.request.reviewed_by, "reviewer-02")
        self.assertIsNotNone(self.request.reviewed_at)



if __name__ == "__main__":
    unittest.main()
