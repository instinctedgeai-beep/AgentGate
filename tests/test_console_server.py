import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from console_server import ApiError, Console, make_handler


class ConsoleStateTests(unittest.TestCase):
    def setUp(self):
        self.console = Console()

    def test_route_records_metadata_without_prompt(self):
        entry = self.console.route("Review confidential merger negotiations.")
        self.assertEqual(entry["route"], "PRIVATE")
        self.assertEqual(entry["status"], "SIMULATED")
        self.assertNotIn("prompt", entry)
        self.assertNotIn("merger", json.dumps(self.console.audit()))

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ApiError):
            self.console.route("hello", mode="cloud")

    def test_execution_failure_is_recorded_not_raised(self):
        import console_server
        original = console_server.execute
        console_server.execute = lambda *a, **k: (_ for _ in ()).throw(ImportError("No module named 'openai'"))
        try:
            entry = self.console.route("Review confidential merger negotiations.", mode="live")
        finally:
            console_server.execute = original
        self.assertEqual(entry["status"], "ERROR")
        self.assertIn("delivery status cannot be confirmed", entry["response"])
        self.assertEqual(len(self.console.history), 1)

    def test_demo_produces_both_routes(self):
        routes = {e["route"] for e in self.console.demo()}
        self.assertEqual(routes, {"CLOUD", "PRIVATE"})

    def test_approval_lifecycle_is_single_use(self):
        call = self.console.call_tool("lookup_customer", {"customer_id": "CUST-1001"})
        self.assertEqual(call["status"], "APPROVAL_REQUIRED")
        approval_id = call["approval_id"]
        with self.assertRaises(ApiError):
            self.console.decide(approval_id, "execute")
        self.console.decide(approval_id, "approve")
        done = self.console.decide(approval_id, "execute")
        self.assertEqual(done["status"], "CONSUMED")
        self.assertEqual(done["outcome"]["status"], "COMPLETED")
        with self.assertRaises(ApiError):
            self.console.decide(approval_id, "execute")

    def test_rejected_request_cannot_execute(self):
        approval_id = self.console.call_tool("lookup_customer", {"customer_id": "CUST-1001"})["approval_id"]
        self.console.decide(approval_id, "reject")
        with self.assertRaises(ApiError):
            self.console.decide(approval_id, "execute")

    def test_agent_history_does_not_store_private_content(self):
        import sys
        from types import ModuleType
        from unittest.mock import patch
        stub = ModuleType("nemotron_agent")
        stub.run_agent = lambda prompt: {
            "status": "BLOCKED", "reason": "Denied",
            "answer": "PRIVATE ANSWER", "tools": [{"result": {"secret": "secret"}}],
            "audit": {"request_id": "test-123", "duration_ms": 1.5,
                      "events": [{"event_type": "PROMPT_INSPECTION", "status": "PRIVATE",
                                  "timestamp": "2026-01-01T00:00:00+00:00",
                                  "detail": "user@example.com"}]}}
        with patch.dict(sys.modules, {"nemotron_agent": stub}):
            self.console.agent("user@example.com")
        saved = json.dumps(self.console.snapshot()["agent_history"])
        self.assertNotIn("user@example.com", saved)
        self.assertNotIn("PRIVATE ANSWER", saved)
        self.assertNotIn("secret", saved)
        self.assertEqual(len(self.console.snapshot()["agent_history"]), 1)

    def test_blocked_tool_creates_no_approval(self):
        call = self.console.call_tool("draft_email", {"recipient": "x@external.example",
                                                       "subject": "s", "body": "b"})
        self.assertEqual(call["status"], "BLOCKED")
        self.assertIsNone(call["approval_id"])
        self.assertEqual(self.console.snapshot()["approvals"], [])


class ConsoleHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.console = Console()
        cls.console.reviewer_auth.reviewer_id = "test-reviewer"
        cls.console.reviewer_auth.reviewer_secret = "synthetic-test-secret"

        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(cls.console),
        )
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()


    def request(self, path, body=None, token=None):
        data = None if body is None else json.dumps(body).encode()

        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(
            self.base + path,
            data=data,
            method="POST" if data is not None else "GET",
            headers=headers,
        )

        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({})
        )

        try:
            with opener.open(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())


    def test_status_and_route(self):
        status, body = self.request("/api/status")
        self.assertEqual(status, 200)
        self.assertGreater(body["patterns"], 0)
        status, body = self.request("/api/route", {"prompt": "Explain SQL joins.", "mode": "simulate"})
        self.assertEqual((status, body["route"]), (200, "CLOUD"))

    def test_bad_input_returns_error(self):
        self.assertEqual(self.request("/api/route", {"prompt": "   "})[0], 400)
        self.assertEqual(self.request("/api/approvals/0000000000000000/approve", {})[0], 401)
        self.assertEqual(self.request("/api/unknown")[0], 404)

    def test_unauthenticated_approval_actions_are_rejected(self):
        for action in ("approve", "reject"):
            with self.subTest(action=action):
                status, _ = self.request(
                    f"/api/approvals/0000000000000000/{action}",
                    {},
                )
                self.assertEqual(status, 401)

    def test_unauthenticated_execution_is_rejected(self):
        status, _ = self.request(
            "/api/approvals/0000000000000000/execute",
            {},
        )
        self.assertEqual(status, 401)


    def test_authenticated_approval_workflow(self):
        # Invalid credentials must fail.
        status, _ = self.request(
            "/api/reviewer/login",
            {"secret": "wrong-secret"},
        )
        self.assertEqual(status, 401)

        # Login with synthetic reviewer credentials.
        status, login = self.request(
            "/api/reviewer/login",
            {"secret": "synthetic-test-secret"},
        )
        self.assertEqual(status, 200)
        token = login["token"]

        # Generate a restricted tool request.
        status, call = self.request(
            "/api/tools/call",
            {
                "tool": "lookup_customer",
                "arguments": {"customer_id": "CUST-1001"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(call["status"], "APPROVAL_REQUIRED")
        approval_id = call["approval_id"]

        endpoint = f"/api/approvals/{approval_id}"

        # Unauthorized approval is rejected.
        status, _ = self.request(
            endpoint + "/approve", {}
        )
        self.assertEqual(status, 401)

        # Authenticated reviewer approves.
        status, approval = self.request(
            endpoint + "/approve", {}, token=token
        )
        self.assertEqual(status, 200)
        self.assertEqual(approval["status"], "APPROVED")
        self.assertEqual(approval["reviewed_by"], "test-reviewer")
        self.assertIsNotNone(approval["reviewed_at"])

        # Approved action executes once.
        status, executed = self.request(
            endpoint + "/execute", {}, token=token
        )
        self.assertEqual(status, 200)
        self.assertEqual(executed["status"], "CONSUMED")
        self.assertEqual(
            executed["outcome"]["status"], "COMPLETED"
        )

        # Replay is prohibited.
        status, _ = self.request(
            endpoint + "/execute", {}, token=token
        )
        self.assertEqual(status, 409)

        # Logout invalidates the reviewer session.
        status, logout = self.request(
            "/api/reviewer/logout", {}, token=token
        )
        self.assertEqual(status, 200)
        self.assertTrue(logout["ok"])

        # The old token cannot authorize another decision.
        status, _ = self.request(
            endpoint + "/reject", {}, token=token
        )
        self.assertEqual(status, 401)

    def test_expired_reviewer_session_is_rejected(self):
        status, login = self.request(
            "/api/reviewer/login",
            {"secret": "synthetic-test-secret"},
        )
        self.assertEqual(status, 200)
        token = login["token"]

        # Invalidate the test session by setting its expiry
        # in the past, without waiting 15 minutes.
        reviewer_id, _ = self.console.reviewer_auth.sessions[token]
        self.console.reviewer_auth.sessions[token] = (reviewer_id, 0)

        status, _ = self.request(
            "/api/approvals/0000000000000000/approve",
            {},
            token=token,
        )
        self.assertEqual(status, 401)
        self.assertIsNone(
            self.console.reviewer_auth.authenticate(token)
        )

    def test_logged_out_session_cannot_execute(self):
        status, login = self.request(
            "/api/reviewer/login",
            {"secret": "synthetic-test-secret"},
        )
        self.assertEqual(status, 200)
        token = login["token"]

        status, call = self.request(
            "/api/tools/call",
            {
                "tool": "lookup_customer",
                "arguments": {"customer_id": "CUST-1001"},
            },
        )
        self.assertEqual(status, 200)
        approval_id = call["approval_id"]

        endpoint = f"/api/approvals/{approval_id}"

        status, _ = self.request(
            endpoint + "/approve", {}, token=token
        )
        self.assertEqual(status, 200)

        status, _ = self.request(
            "/api/reviewer/logout", {}, token=token
        )
        self.assertEqual(status, 200)

        # An approved request must not be executable
        # using a session that has been logged out.
        status, _ = self.request(
            endpoint + "/execute", {}, token=token
        )
        self.assertEqual(status, 401)

        # It must also reject execution without a token.
        status, _ = self.request(
            endpoint + "/execute", {}
        )
        self.assertEqual(status, 401)
