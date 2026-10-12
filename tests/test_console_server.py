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
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Console()))
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method="POST" if data is not None else "GET",
                                     headers={"Content-Type": "application/json"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
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
        self.assertEqual(self.request("/api/approvals/0000000000000000/approve", {})[0], 404)
        self.assertEqual(self.request("/api/unknown")[0], 404)
