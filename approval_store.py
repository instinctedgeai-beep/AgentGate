
"""SQLite persistence for AgentGate approval records."""

import json
import sqlite3
from pathlib import Path


class ApprovalStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=10,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        import os

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        if self.db_path.exists():
            os.chmod(self.db_path, 0o600)

        previous_umask = os.umask(0o077)

        try:
            with self._connect() as connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS approvals (
                        approval_id TEXT PRIMARY KEY,
                        tool_name TEXT NOT NULL,
                        arguments_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        reviewed_by TEXT,
                        reviewed_at TEXT,
                        execution_status TEXT
                    )
                """)

                connection.execute("""
                    CREATE TABLE IF NOT EXISTS agent_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id TEXT,
                        status TEXT NOT NULL,
                        duration_ms REAL,
                        timestamp TEXT NOT NULL,
                        events_json TEXT NOT NULL
                    )
                """)
        finally:
            os.umask(previous_umask)

        os.chmod(self.db_path, 0o600)

    def save(self, request, execution_status=None):
        """Save an approval record and its current state."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO approvals (
                    approval_id,
                    tool_name,
                    arguments_json,
                    status,
                    created_at,
                    reviewed_by,
                    reviewed_at,
                    execution_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(approval_id) DO UPDATE SET
                    status = excluded.status,
                    reviewed_by = excluded.reviewed_by,
                    reviewed_at = excluded.reviewed_at,
                    execution_status = excluded.execution_status
                WHERE approvals.status = 'PENDING'
                    AND excluded.status IN ('APPROVED', 'REJECTED')
                """,
                (
                    request.approval_id,
                    request.tool_name,
                    json.dumps(request.arguments),
                    request.status,
                    request.created_at,
                    request.reviewed_by,
                    request.reviewed_at,
                    execution_status,
                ),
            )

    def load_all(self):
        """Return persisted approval records."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    approval_id,
                    tool_name,
                    arguments_json,
                    status,
                    created_at,
                    reviewed_by,
                    reviewed_at,
                    execution_status
                FROM approvals
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [
            {
                "approval_id": row["approval_id"],
                "tool_name": row["tool_name"],
                "arguments": json.loads(row["arguments_json"]),
                "status": row["status"],
                "created_at": row["created_at"],
                "reviewed_by": row["reviewed_by"],
                "reviewed_at": row["reviewed_at"],
                "execution_status": row["execution_status"],
            }
            for row in rows
        ]
    
    def decide(self, approval_id, action, reviewer_id, reviewed_at):
        """Atomically transition a pending approval."""
        if action not in ("APPROVED", "REJECTED"):
            raise ValueError("Invalid approval decision")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approvals
                SET status = ?,
                    reviewed_by = ?,
                    reviewed_at = ?
                WHERE approval_id = ?
                  AND status = 'PENDING'
                """,
                (
                    action,
                    reviewer_id,
                    reviewed_at,
                    approval_id,
                ),
            )
            return cursor.rowcount == 1

    def consume(self, approval_id, tool_name, arguments):
        """Atomically consume an approved request exactly once."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approvals
                SET status = 'CONSUMED',
                    execution_status = 'UNKNOWN'
                WHERE approval_id = ?
                  AND tool_name = ?
                  AND arguments_json = ?
                  AND status = 'APPROVED'
                """,
                (
                    approval_id,
                    tool_name,
                    json.dumps(arguments),
                ),
            )
            return cursor.rowcount == 1

    def record_execution(self, approval_id, execution_status):
        """Record the outcome of an already-consumed approval."""
        if execution_status not in ("COMPLETED", "ERROR", "UNKNOWN"):
            raise ValueError("Invalid execution status")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approvals
                SET execution_status = ?
                WHERE approval_id = ?
                  AND status = 'CONSUMED'
                  AND execution_status = 'UNKNOWN'
                """,
                (execution_status, approval_id),
            )

            return cursor.rowcount == 1

    def save_agent_audit(self, record):
        """Persist allowlisted agent execution metadata."""
        safe = {
            "request_id": record.get("request_id"),
            "status": record.get("status", "ERROR"),
            "duration_ms": record.get("duration_ms"),
            "timestamp": record.get("timestamp"),
            "events": [
                {
                    "event_type": event.get("event_type"),
                    "status": event.get("status"),
                    "timestamp": event.get("timestamp"),
                }
                for event in record.get("events", [])
                if isinstance(event, dict)
            ],
        }

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_audit (
                    request_id, status, duration_ms,
                    timestamp, events_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    safe["request_id"],
                    safe["status"],
                    safe["duration_ms"],
                    safe["timestamp"],
                    json.dumps(safe["events"]),
                ),
            )

    def load_agent_audit(self, limit=200):
        """Restore recent agent metadata, newest first."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT request_id, status, duration_ms,
                       timestamp, events_json
                FROM agent_audit
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "request_id": row["request_id"],
                "status": row["status"],
                "duration_ms": row["duration_ms"],
                "timestamp": row["timestamp"],
                "events": json.loads(row["events_json"]),
            }
            for row in rows
        ]
