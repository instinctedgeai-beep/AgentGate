"""AgentGate Console: a local web control room for the policy engine.

Standard library only. It serves the single-page console in ``web/`` and a
small JSON API over the existing modules (policy_engine, model_client,
tool_gateway, approval_manager), so every decision shown in the UI is made by
the same code the tests cover.

    python console_server.py            # http://127.0.0.1:8600
    python console_server.py --port 9000

State is in memory and per server process. Raw prompts are never stored.
"""

import argparse
import json
import os
import re
import threading
import secrets
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from approval_manager import ApprovalManager
from dashboard_data import DEMO_PROMPTS, SAMPLE_PROMPTS, TOOL_FIELDS, TOOL_POLICY_MATRIX, TOOL_PRESETS
from engine import PATTERNS, execute, inspect
from tool_gateway import run_tool
from reviewer_auth import ReviewerAuth

try:  # optional, mirrors nemotron_agent.py
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
MAX_BODY = 64 * 1024
AUDIT_FIELDS = ["timestamp", "request_id", "route", "policy_id", "signals", "reason", "inspection_ms",
                "execution_mode", "status", "inference_ms", "tokens", "cost_usd"]


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(body: dict, key: str, limit: int = 4000) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, f"'{key}' must be a non-empty string")
    if len(value) > limit:
        raise ApiError(413, f"'{key}' is longer than {limit} characters")
    return value


class Console:
    """All dashboard state and actions, independent of HTTP."""

    def __init__(self):
        self.lock = threading.Lock()
        self.history = []          # newest first, decision metadata + execution result
        self.approvals = ApprovalManager()
        self.tool_log = []         # newest first
        self.results = {}          # approval_id -> execution outcome
        self.agent_history = []   # metadata only; never store prompts or tool outputs
        self.reviewer_auth = ReviewerAuth()
        self.status_tokens = {}  # Random status token -> approval ID

    # -- read models -------------------------------------------------------
    def status(self) -> dict:
        nim = os.getenv("PRIVATE_NIM_BASE_URL", "")
        summary_file = ROOT / "summary.json"
        tests = sum(len(re.findall(r"^\s+def test_", f.read_text(), re.M))
                    for f in (ROOT / "tests").glob("test_*.py"))
        return {
            "hosted_key": bool(os.getenv("NVIDIA_API_KEY")),
            "private_nim": nim.startswith(("http://localhost:", "http://127.0.0.1:")),  # configured, not health-checked
            "patterns": len(PATTERNS),
            "tests": tests,
            "summary": json.loads(summary_file.read_text()) if summary_file.exists() else None,
            "samples": SAMPLE_PROMPTS,
            "tools": TOOL_FIELDS,
            "presets": {k: {"tool": t, "arguments": a} for k, (t, a) in TOOL_PRESETS.items()},
            "policy": [{"tool": t, "condition": c, "outcome": o} for t, c, o in TOOL_POLICY_MATRIX],
        }


    def public_snapshot(self) -> dict:
        """Return limited operational counts, never approval details."""
        with self.lock:
            pending = sum(
                req.status == "PENDING"
                for req in self.approvals.requests.values()
            )
            return {
                "pending_approvals": pending,
                "total_requests": len(self.history),
                "recent_tool_statuses": [
                    {
                        "status": item["status"],
                        "time": item["time"],
                    }
                    for item in self.tool_log[:10]
                ],
            }

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "history": list(self.history),
                "approvals": [self._approval(r) for r in sorted(
                    self.approvals.requests.values(), key=lambda r: r.created_at, reverse=True)],
                "tool_log": [
                    {
                        "time": item["time"],
                        "tool": item["tool"],
                        "status": item["status"],
                        "reason": item["reason"],
                    }
                    for item in self.tool_log
                ],
                "agent_history": list(self.agent_history),
            }

    def _approval(self, req) -> dict:
        outcome = self.results.get(req.approval_id)

        execution_status = (
            outcome.get("status")
            if isinstance(outcome, dict)
            else None
        )

        return {
            "approval_id": req.approval_id,
            "tool": req.tool_name,
            "arguments": req.arguments,
            "status": req.status,
            "created_at": req.created_at,
            "execution_status": execution_status,
            "reviewed_by": req.reviewed_by,
            "reviewed_at": req.reviewed_at,
        }


    def evaluation(self) -> dict:
        import csv
        cases_file = ROOT / "results.csv"
        cases = []
        if cases_file.exists():
            with cases_file.open(newline="") as fp:
                cases = list(csv.DictReader(fp))
        return {"summary": self.status()["summary"], "cases": cases}

    def audit(self) -> list:
        with self.lock:
            return [{f: r.get(f) for f in AUDIT_FIELDS} for r in self.history]

    # -- actions -----------------------------------------------------------
    def route(self, prompt: str, mode: str = "simulate") -> dict:
        if mode not in ("simulate", "live"):
            raise ApiError(400, "mode must be 'simulate' or 'live'")
        decision = inspect(prompt)
        try:
            result = execute(prompt, decision, mode=mode)
        except Exception as exc:  # e.g. the openai package missing in live mode; record it as held
            result = {"status": "ERROR", "response": "Inference failed; delivery status cannot be confirmed.",
                      "inference_ms": None, "tokens": None, "cost_usd": None}
        entry = {**decision.__dict__, **result, "execution_mode": mode}
        with self.lock:
            self.history.insert(0, entry)
            del self.history[500:]
        return entry

    def demo(self) -> list:
        return [self.route(p, "simulate") for p in DEMO_PROMPTS]

    def clear(self) -> None:
        with self.lock:
            self.history.clear()

    def call_tool(self, tool: str, arguments) -> dict:
        outcome = run_tool(tool, arguments)
        entry = {"time": _now(), "tool": tool, "arguments": arguments if isinstance(arguments, dict) else {},
                 "status": outcome["status"], "reason": outcome["reason"], "approval_id": None,
                 "result": outcome.get("result")}

        status_token = None
        with self.lock:
            if outcome["status"] == "APPROVAL_REQUIRED":
                request = self.approvals.create_request(tool, arguments)
                entry["approval_id"] = request.approval_id

                # Separate, unpredictable capability for checking status.
                status_token = secrets.token_urlsafe(32)
                self.status_tokens[status_token] = request.approval_id

            self.tool_log.insert(0, entry)
            del self.tool_log[200:]

        # The status token must not be written into shared tool logs.
        response = dict(entry)
        if status_token is not None:
            response["status_token"] = status_token

        return response

    def request_status(self, token: str) -> dict:
        """Return only the approval state for a specific status token."""
        with self.lock:
            approval_id = self.status_tokens.get(token)

            if approval_id is None:
                raise ApiError(404, "Request status not found")

            request = self.approvals.requests.get(approval_id)

            if request is None:
                raise ApiError(404, "Request status not found")

            execution = self.results.get(approval_id)
            execution_status = (
                execution.get("status")
                if isinstance(execution, dict)
                else None
            )

            return {
                "status": request.status,
                "execution_status": execution_status,
            }

    def decide(self, approval_id: str, action: str, reviewer_id: str | None = None) -> dict:
        with self.lock:
            req = self.approvals.requests.get(approval_id)
            if req is None:
                raise ApiError(404, "Unknown approval request")
            if action == "approve":
                ok = self.approvals.approve(approval_id, reviewer_id=reviewer_id)
            elif action == "reject":
                ok = self.approvals.reject(approval_id, reviewer_id=reviewer_id)
            elif action == "execute":
                outcome = run_tool(req.tool_name, req.arguments, approval_id=approval_id,
                                   approval_manager=self.approvals)
                ok = outcome["status"] == "COMPLETED"
                self.results[approval_id] = outcome
                self.tool_log.insert(0, {"time": _now(), "tool": req.tool_name, "arguments": req.arguments,
                                         "status": outcome["status"], "approval_id": approval_id,
                                         "reason": "Executed with single-use approval" if ok else outcome["reason"],
                                         "result": outcome.get("result")})
            else:
                raise ApiError(400, "action must be approve, reject or execute")
            if not ok:
                raise ApiError(
                    409,
                    f"Cannot {action} a request that is {req.status.lower()}",
                )

            response = self._approval(req)

            if action == "execute":
                response["outcome"] = {
                    "status": outcome["status"],
                }

            return response


    def agent(self, prompt: str) -> dict:
        try:
            from nemotron_agent import run_agent
        except ImportError:
            result = {"status": "ERROR", "reason": "Agent dependencies are unavailable"}
        else:
            try:
                result = run_agent(prompt)
            except Exception:
                result = {"status": "ERROR", "reason": "Agent execution failed; check local server logs"}
        audit = result.get("audit") if isinstance(result.get("audit"), dict) else {}
        events = audit.get("events", [])
        # Strictly allowlist metadata fields; never persist prompts, tool results or arguments.
        safe_events = [{"event_type": str(e.get("event_type", ""))[:48],
                        "status": str(e.get("status", ""))[:40],
                        "timestamp": str(e.get("timestamp", ""))[:60]}
                       for e in events if isinstance(e, dict)]
        duration = audit.get("duration_ms")
        duration = duration if isinstance(duration, (int, float)) and not isinstance(duration, bool) else None
        record = {"request_id": str(audit.get("request_id", ""))[:64] or None,
                  "status": result.get("status", "ERROR"),
                  "duration_ms": duration,
                  "timestamp": _now(), "events": safe_events}
        with self.lock:
            self.agent_history.insert(0, record)
            del self.agent_history[200:]
        return result


def make_handler(console: Console):
    class Handler(SimpleHTTPRequestHandler):
        server_version = "AgentGateConsole/1.0"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB), **kwargs)

        def log_message(self, fmt, *args):  # keep the terminal quiet; prompts never logged
            pass

        def end_headers(self):
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if self.path.startswith("/api/"):
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _json(self, status: int, payload, filename: str = None):
            data = json.dumps(payload, indent=2 if filename else None).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ApiError(413, "Request body too large")
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                raise ApiError(400, "Body must be JSON")
            if not isinstance(body, dict):
                raise ApiError(400, "Body must be a JSON object")
            return body

        def _dispatch(self, method: str):
            if method == "POST":
                # Local-only prototype: prevent cross-origin browser writes.
                origin = self.headers.get("Origin")
                expected = f"http://{self.headers.get('Host', '')}"
                if origin and origin != expected:
                    return self._json(403, {"error": "Cross-origin writes are not permitted"})
            path = urlparse(self.path).path.rstrip("/")
            try:
                if method == "GET":
                    if path == "/api/status":
                        return self._json(200, console.status())

                    if path == "/api/public-state":
                        return self._json(200, console.public_snapshot())

                    if path in (
                        "/api/state",
                        "/api/audit.json",
                    ):
                        authorization = self.headers.get(
                            "Authorization", ""
                        )
                        scheme, _, token = authorization.partition(" ")

                        if scheme != "Bearer" or not token:
                            raise ApiError(
                                401,
                                "Reviewer authentication required",
                            )

                        reviewer_id = console.reviewer_auth.authenticate(
                            token
                        )

                        if reviewer_id is None:
                            raise ApiError(
                                401,
                                "Reviewer session invalid or expired",
                            )

                        if path == "/api/state":
                            return self._json(200, console.snapshot())

                        return self._json(
                            200,
                            console.audit(),
                            filename="agentgate-audit.json",
                        )

                    if path == "/api/evaluation":
                        return self._json(200, console.evaluation())

                    raise ApiError(404, "Not found")

                body = self._body()
                if path == "/api/reviewer/login":
                    token = console.reviewer_auth.login(body.get("secret"))
                    if token is None:
                        raise ApiError(401, "Invalid reviewer credentials")
                    return self._json(200, {
                        "token": token,
                        "expires_in": console.reviewer_auth.session_seconds,
                    })
                if path == "/api/reviewer/logout":
                    authorization = self.headers.get("Authorization", "")
                    scheme, _, token = authorization.partition(" ")

                    if scheme != "Bearer" or not token:
                        raise ApiError(401, "Reviewer authentication required")

                    reviewer_id = console.reviewer_auth.authenticate(token)

                    if reviewer_id is None:
                        raise ApiError(401, "Reviewer session invalid or expired")

                    console.reviewer_auth.logout(token)
                    return self._json(200, {"ok": True})
                if path == "/api/route":
                    return self._json(200, console.route(_text(body, "prompt"), body.get("mode", "simulate")))
                if path == "/api/demo":
                    return self._json(200, console.demo())
                if path == "/api/clear":
                    console.clear()
                    return self._json(200, {"ok": True})
                if path == "/api/tools/call":
                    return self._json(
                        200,
                        console.call_tool(
                            _text(body, "tool", 64),
                            body.get("arguments"),
                        ),
                    )
                if path == "/api/request-status":
                    token = _text(body, "status_token", 256)
                    return self._json(
                        200,
                        console.request_status(token),
                    )
                m = re.fullmatch(
                    r"/api/approvals/([0-9a-f]{16})/(approve|reject|execute)",
                    path,
                )

                if m:
                    action = m.group(2)

                    authorization = self.headers.get("Authorization", "")
                    scheme, _, token = authorization.partition(" ")

                    if scheme != "Bearer" or not token:
                        raise ApiError(401, "Reviewer authentication required")

                    reviewer_id = console.reviewer_auth.authenticate(token)

                    if reviewer_id is None:
                        raise ApiError(401, "Reviewer session invalid or expired")

                    return self._json(
                        200,
                        console.decide(
                            m.group(1),
                            action,
                            reviewer_id=reviewer_id,
                        ),
                    )

                if path == "/api/agent":
                    return self._json(200, console.agent(_text(body, "prompt")))
                raise ApiError(404, "Not found")
            except ApiError as err:
                return self._json(err.status, {"error": str(err)})
            except Exception as exc:  # never leave the browser with a broken response
                return self._json(500, {"error": f"Server error: {type(exc).__name__}"})

        def do_GET(self):
            if self.path.startswith("/api/"):
                return self._dispatch("GET")
            return super().do_GET()

        def do_POST(self):
            return self._dispatch("POST")

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Run the AgentGate web console.")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost only)")
    parser.add_argument("--port", type=int, default=8600)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        parser.error("This unauthenticated prototype must bind to localhost only")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(Console()))
    print(f"AgentGate Console running at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
