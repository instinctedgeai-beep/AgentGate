
"""HTTP regression tests for protected record removal."""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from approval_store import ApprovalStore
from console_server import Console, make_handler
from http.server import ThreadingHTTPServer


class DeletionHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "test-approvals.db"

        self.console = Console(db_path=self.db_path)
        self.console.reviewer_auth.reviewer_id = "test-reviewer"
        self.console.reviewer_auth.reviewer_secret = "test-login-secret"
        self.console.reviewer_auth.deletion_code = "042681"
        self.console.reviewer_auth.employee_id = "EMP-TEST"

        self.token = self.console.reviewer_auth.login(
            "test-login-secret"
        )
        self.assertIsNotNone(self.token)

        request = self.console.call_tool(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )
        self.approval_id = request["approval_id"]

        self.console.decide(
            self.approval_id,
            "reject",
            reviewer_id="test-reviewer",
        )

        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(self.console),
        )
        self.base = (
            f"http://127.0.0.1:{self.server.server_address[1]}"
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, path, body, token=None):
        headers = {"Content-Type": "application/json"}

        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )

        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({})
        )

        try:
            with opener.open(req, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def hide(self, code, reason, token=None):
        return self.request(
            f"/api/approvals/{self.approval_id}/hide",
            {
                "deletion_code": code,
                "reason": reason,
            },
            token=token,
        )

    def test_removal_requires_reviewer_session(self):
        status, _ = self.hide(
            "042681",
            "Duplicate request",
        )

        self.assertEqual(status, 401)
        self.assertIn(
            self.approval_id,
            self.console.store.visible_approval_ids(),
        )

    def test_incorrect_code_preserves_record_and_session(self):
        status, _ = self.hide(
            "999999",
            "Duplicate request",
            token=self.token,
        )

        self.assertEqual(status, 401)
        self.assertEqual(
            self.console.reviewer_auth.authenticate(self.token),
            "test-reviewer",
        )
        self.assertIn(
            self.approval_id,
            self.console.store.visible_approval_ids(),
        )
        self.assertEqual(self.console.store.deleted_records(), [])

    def test_reason_over_100_characters_is_rejected(self):
        status, _ = self.hide(
            "042681",
            "X" * 101,
            token=self.token,
        )

        self.assertEqual(status, 400)
        self.assertIn(
            self.approval_id,
            self.console.store.visible_approval_ids(),
        )

    def test_successful_removal_preserves_audit_and_identity(self):
        reason = "Duplicate request"

        status, result = self.hide(
            "042681",
            reason,
            token=self.token,
        )

        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])

        self.assertNotIn(
            self.approval_id,
            self.console.store.visible_approval_ids(),
        )

        reopened = ApprovalStore(self.db_path)
        deleted = reopened.deleted_records()

        self.assertEqual(len(deleted), 1)
        self.assertEqual(
            deleted[0]["request_id"],
            self.approval_id,
        )
        self.assertEqual(
            deleted[0]["deleted_by"],
            "test-reviewer",
        )
        self.assertEqual(
            deleted[0]["employee_id"],
            "EMP-TEST",
        )
        self.assertEqual(deleted[0]["reason"], reason)
        self.assertTrue(deleted[0]["deleted_at"])

        original = next(
            record
            for record in reopened.load_all()
            if record["approval_id"] == self.approval_id
        )

        self.assertEqual(original["status"], "REJECTED")
        self.assertEqual(
            original["reviewed_by"],
            "test-reviewer",
        )


if __name__ == "__main__":
    unittest.main()
