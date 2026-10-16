
"""Human approval management for AgentGate."""

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ApprovalRequest:
    approval_id: str
    tool_name: str
    arguments: dict
    status: str = "PENDING"
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class ApprovalManager:
    def __init__(self, store=None):
        self.requests = {}
        self.store = store

        if self.store is not None:
            for record in self.store.load_all():
                request = ApprovalRequest(
                    approval_id=record["approval_id"],
                    tool_name=record["tool_name"],
                    arguments=record["arguments"],
                    status=record["status"],
                    reviewed_by=record["reviewed_by"],
                    reviewed_at=record["reviewed_at"],
                    created_at=record["created_at"],
                )
                self.requests[request.approval_id] = request

    def create_request(self, tool_name, arguments):
        approval_id = secrets.token_hex(8)

        request = ApprovalRequest(
            approval_id=approval_id,
            tool_name=tool_name,
            arguments=arguments.copy(),
        )

        self.requests[approval_id] = request
        if self.store is not None:
            self.store.save(request)
        return request

    def approve(self, approval_id, reviewer_id=None):
        request = self.requests.get(approval_id)

        if request is None or request.status != "PENDING":
            return False

        reviewed_at = datetime.now(timezone.utc).isoformat()

        if self.store is not None:
            if not self.store.decide(
                approval_id,
                "APPROVED",
                reviewer_id,
                reviewed_at,
            ):
                return False

        request.status = "APPROVED"
        request.reviewed_by = reviewer_id
        request.reviewed_at = reviewed_at
        return True

    def reject(self, approval_id, reviewer_id=None):
        request = self.requests.get(approval_id)

        if request is None or request.status != "PENDING":
            return False

        reviewed_at = datetime.now(timezone.utc).isoformat()

        if self.store is not None:
            if not self.store.decide(
                approval_id,
                "REJECTED",
                reviewer_id,
                reviewed_at,
            ):
                return False

        request.status = "REJECTED"
        request.reviewed_by = reviewer_id
        request.reviewed_at = reviewed_at
        return True

    def consume(self, approval_id, tool_name, arguments):
        """Consume an approved request exactly once."""

        request = self.requests.get(approval_id)

        if request is None or request.status != "APPROVED":
            return False

        if request.tool_name != tool_name:
            return False

        if request.arguments != arguments:
            return False

        if self.store is not None:
            # SQLite must commit consumption before tool execution.
            if not self.store.consume(
                approval_id,
                tool_name,
                arguments,
            ):
                return False

        request.status = "CONSUMED"
        return True
