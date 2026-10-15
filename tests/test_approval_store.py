
import tempfile
import unittest
from pathlib import Path

from approval_manager import ApprovalManager
from approval_store import ApprovalStore


class ApprovalStoreTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "approvals.db"
        self.store = ApprovalStore(self.db_path)

        self.manager = ApprovalManager()
        self.request = self.manager.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_creates_database(self):
        self.assertTrue(self.db_path.exists())

    def test_saves_pending_request(self):
        self.store.save(self.request)

        records = self.store.load_all()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "PENDING")
        self.assertEqual(
            records[0]["arguments"],
            {"customer_id": "CUST-1001"},
        )

    def test_saves_approval_decision(self):
        self.store.save(self.request)

        self.manager.approve(
            self.request.approval_id,
            reviewer_id="reviewer-test",
        )
        self.store.save(self.request)

        records = self.store.load_all()

        self.assertEqual(records[0]["status"], "APPROVED")
        self.assertEqual(
            records[0]["reviewed_by"],
            "reviewer-test",
        )

    def test_records_execution_status(self):
        self.manager.approve(self.request.approval_id)
        self.manager.consume(
            self.request.approval_id,
            self.request.tool_name,
            self.request.arguments,
        )

        self.store.save(
            self.request,
            execution_status="COMPLETED",
        )

        records = self.store.load_all()

        self.assertEqual(records[0]["status"], "CONSUMED")
        self.assertEqual(
            records[0]["execution_status"],
            "COMPLETED",
        )

    def test_records_survive_reopening(self):
        self.store.save(self.request)

        reopened = ApprovalStore(self.db_path)
        records = reopened.load_all()

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0]["approval_id"],
            self.request.approval_id,
        )

    def test_approved_request_consumes_once(self):
        self.manager.approve(self.request.approval_id)
        self.store.save(self.request)

        first = self.store.consume(
            self.request.approval_id,
            self.request.tool_name,
            self.request.arguments,
        )

        second = self.store.consume(
            self.request.approval_id,
            self.request.tool_name,
            self.request.arguments,
        )

        self.assertTrue(first)
        self.assertFalse(second)

        record = self.store.load_all()[0]
        self.assertEqual(record["status"], "CONSUMED")
        self.assertEqual(record["execution_status"], "UNKNOWN")

    def test_consumption_survives_restart(self):
        self.manager.approve(self.request.approval_id)
        self.store.save(self.request)

        self.assertTrue(
            self.store.consume(
                self.request.approval_id,
                self.request.tool_name,
                self.request.arguments,
            )
        )

        reopened = ApprovalStore(self.db_path)

        self.assertFalse(
            reopened.consume(
                self.request.approval_id,
                self.request.tool_name,
                self.request.arguments,
            )
        )

    def test_pending_request_cannot_execute(self):
        self.store.save(self.request)

        self.assertFalse(
            self.store.consume(
                self.request.approval_id,
                self.request.tool_name,
                self.request.arguments,
            )
        )

    def test_changed_arguments_cannot_execute(self):
        self.manager.approve(self.request.approval_id)
        self.store.save(self.request)

        self.assertFalse(
            self.store.consume(
                self.request.approval_id,
                self.request.tool_name,
                {"customer_id": "CUST-9999"},
            )
        )
    
    def test_stale_save_cannot_restore_consumed_approval(self):
        self.manager.approve(self.request.approval_id)
        self.store.save(self.request)

        self.assertTrue(
            self.store.consume(
                self.request.approval_id,
                self.request.tool_name,
                self.request.arguments,
            )
        )

        # The in-memory request still says APPROVED.
        self.store.save(self.request)

        record = self.store.load_all()[0]
        self.assertEqual(record["status"], "CONSUMED")
        self.assertEqual(record["execution_status"], "UNKNOWN")

    def test_stale_save_cannot_reverse_rejection(self):
        self.store.save(self.request)
        self.manager.reject(self.request.approval_id, reviewer_id="reviewer")
        self.store.save(self.request)

        stale = self.manager.requests[self.request.approval_id]
        stale.status = "PENDING"
        self.store.save(stale)

        self.assertEqual(self.store.load_all()[0]["status"], "REJECTED")

    def test_execution_outcome_recorded_once(self):
        self.manager.approve(self.request.approval_id)
        self.store.save(self.request)

        self.assertTrue(
            self.store.consume(
                self.request.approval_id,
                self.request.tool_name,
                self.request.arguments,
            )
        )

        self.assertTrue(
            self.store.record_execution(
                self.request.approval_id,
                "COMPLETED",
            )
        )

        self.assertFalse(
            self.store.record_execution(
                self.request.approval_id,
                "ERROR",
            )
        )

        record = self.store.load_all()[0]
        self.assertEqual(record["execution_status"], "COMPLETED")
    def test_manager_restores_pending_approval(self):
        manager = ApprovalManager(store=self.store)
        request = manager.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        restored = ApprovalManager(
            store=ApprovalStore(self.db_path)
        )

        self.assertEqual(
            restored.requests[request.approval_id].status,
            "PENDING",
        )

    def test_manager_restores_reviewer_decision(self):
        manager = ApprovalManager(store=self.store)
        request = manager.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        manager.approve(
            request.approval_id,
            reviewer_id="reviewer-test",
        )

        restored = ApprovalManager(
            store=ApprovalStore(self.db_path)
        )

        saved = restored.requests[request.approval_id]

        self.assertEqual(saved.status, "APPROVED")
        self.assertEqual(saved.reviewed_by, "reviewer-test")

    def test_persistent_manager_consumes_approval_once(self):
        manager = ApprovalManager(store=self.store)

        request = manager.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        manager.approve(request.approval_id, reviewer_id="reviewer-test")

        self.assertTrue(
            manager.consume(
                request.approval_id,
                request.tool_name,
                request.arguments,
            )
        )

        self.assertFalse(
            manager.consume(
                request.approval_id,
                request.tool_name,
                request.arguments,
            )
        )

        restored = ApprovalManager(
            store=ApprovalStore(self.db_path)
        )

        self.assertEqual(
            restored.requests[request.approval_id].status,
            "CONSUMED",
        )

        self.assertFalse(
            restored.consume(
                request.approval_id,
                request.tool_name,
                request.arguments,
            )
        )

    def test_two_managers_cannot_consume_same_approval(self):
        first = ApprovalManager(store=self.store)

        request = first.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        first.approve(request.approval_id)

        second = ApprovalManager(
            store=ApprovalStore(self.db_path)
        )

        self.assertTrue(
            first.consume(
                request.approval_id,
                request.tool_name,
                request.arguments,
            )
        )

        self.assertFalse(
            second.consume(
                request.approval_id,
                request.tool_name,
                request.arguments,
            )
        )

    def test_failed_persistent_consumption_does_not_change_memory(self):
        manager = ApprovalManager(store=self.store)

        request = manager.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        manager.approve(request.approval_id)

        self.assertFalse(
            manager.consume(
                request.approval_id,
                request.tool_name,
                {"customer_id": "CUST-9999"},
            )
        )

        self.assertEqual(request.status, "APPROVED")
        self.assertEqual(
            self.store.load_all()[0]["status"],
            "APPROVED",
        )
    def test_console_restores_approval_after_restart(self):
        from console_server import Console

        first = Console(db_path=self.db_path)

        request = first.approvals.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        first.approvals.approve(
            request.approval_id,
            reviewer_id="reviewer-test",
        )

        restored = Console(db_path=self.db_path)

        self.assertEqual(
            restored.approvals.requests[request.approval_id].status,
            "APPROVED",
        )

    def test_console_restores_consumed_state(self):
        from console_server import Console

        first = Console(db_path=self.db_path)

        request = first.approvals.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        first.approvals.approve(request.approval_id)

        self.assertTrue(
            first.approvals.consume(
                request.approval_id,
                request.tool_name,
                request.arguments,
            )
        )

        restored = Console(db_path=self.db_path)

        self.assertEqual(
            restored.approvals.requests[request.approval_id].status,
            "CONSUMED",
        )

        self.assertFalse(
            restored.approvals.consume(
                request.approval_id,
                request.tool_name,
                request.arguments,
            )
        )
    def test_rejected_request_remains_rejected_after_restart(self):
        manager = ApprovalManager(store=self.store)

        request = manager.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        self.assertTrue(
            manager.reject(
                request.approval_id,
                reviewer_id="reviewer-test",
            )
        )

        restarted = ApprovalManager(
            store=ApprovalStore(self.db_path)
        )

        restored = restarted.requests[request.approval_id]

        self.assertEqual(restored.status, "REJECTED")
        self.assertEqual(restored.reviewed_by, "reviewer-test")

        self.assertFalse(
            restarted.consume(
                request.approval_id,
                request.tool_name,
                request.arguments,
            )
        )
    
    def test_two_managers_cannot_make_conflicting_decisions(self):
        first = ApprovalManager(store=self.store)

        request = first.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        second = ApprovalManager(
            store=ApprovalStore(self.db_path)
        )

        self.assertTrue(
            first.approve(
                request.approval_id,
                reviewer_id="reviewer-one",
            )
        )

        self.assertFalse(
            second.reject(
                request.approval_id,
                reviewer_id="reviewer-two",
            )
        )

        restarted = ApprovalManager(
            store=ApprovalStore(self.db_path)
        )

        saved = restarted.requests[request.approval_id]

        self.assertEqual(saved.status, "APPROVED")
        self.assertEqual(saved.reviewed_by, "reviewer-one")

    def test_failed_decision_does_not_change_memory(self):
        first = ApprovalManager(store=self.store)

        request = first.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        second = ApprovalManager(
            store=ApprovalStore(self.db_path)
        )

        self.assertTrue(first.reject(request.approval_id))

        self.assertFalse(
            second.approve(request.approval_id)
        )

        self.assertEqual(
            second.requests[request.approval_id].status,
            "PENDING",
        )

        restored = ApprovalManager(
            store=ApprovalStore(self.db_path)
        )

        self.assertEqual(
            restored.requests[request.approval_id].status,
            "REJECTED",
        )
    def test_stale_save_cannot_change_approved_record(self):
        manager = ApprovalManager(store=self.store)

        request = manager.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )

        self.assertTrue(
            manager.approve(
                request.approval_id,
                reviewer_id="reviewer-one",
            )
        )

        request.reviewed_by = "different-reviewer"
        request.status = "APPROVED"

        self.store.save(request)

        restored = ApprovalStore(self.db_path).load_all()[0]

        self.assertEqual(restored["status"], "APPROVED")
        self.assertEqual(restored["reviewed_by"], "reviewer-one")
        
    def test_agent_audit_survives_restart_without_private_content(self):
        record = {
            "request_id": "audit-test-001",
            "status": "BLOCKED",
            "duration_ms": 2.5,
            "timestamp": "2026-10-15T12:00:00+00:00",
            "events": [
                {
                    "event_type": "TOOL_POLICY",
                    "status": "BLOCKED",
                    "timestamp": "2026-10-15T12:00:00+00:00",
                    "detail": "private-customer-information",
                }
            ],
            "answer": "private-tool-result",
        }

        self.store.save_agent_audit(record)

        reopened = ApprovalStore(self.db_path)
        restored = reopened.load_agent_audit()

        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["status"], "BLOCKED")
        self.assertEqual(
            restored[0]["events"][0]["event_type"],
            "TOOL_POLICY",
        )

        import json
        saved = json.dumps(restored)

        self.assertNotIn("private-customer-information", saved)
        self.assertNotIn("private-tool-result", saved)

    def test_console_restores_agent_audit_after_restart(self):
        from console_server import Console

        first = Console(db_path=self.db_path)

        first.store.save_agent_audit({
            "request_id": "restart-audit-001",
            "status": "BLOCKED",
            "duration_ms": 1.8,
            "timestamp": "2026-10-15T12:00:00+00:00",
            "events": [
                {
                    "event_type": "TOOL_POLICY",
                    "status": "BLOCKED",
                    "timestamp": "2026-10-15T12:00:00+00:00",
                }
            ],
        })

        restarted = Console(db_path=self.db_path)

        self.assertEqual(len(restarted.agent_history), 1)
        self.assertEqual(
            restarted.agent_history[0]["status"],
            "BLOCKED",
        )
if __name__ == "__main__":
    unittest.main()
