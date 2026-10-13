
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
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class ApprovalManager:
    def __init__(self):
        self.requests = {}

    def create_request(self, tool_name, arguments):
        approval_id = secrets.token_hex(8)

        request = ApprovalRequest(
            approval_id=approval_id,
            tool_name=tool_name,
            arguments=arguments.copy(),
        )

        self.requests[approval_id] = request
        return request

    def approve(self, approval_id):
        request = self.requests.get(approval_id)

        if request is None or request.status != "PENDING":
            return False

        request.status = "APPROVED"
        return True

    def reject(self, approval_id):
        request = self.requests.get(approval_id)

        if request is None or request.status != "PENDING":
            return False

        request.status = "REJECTED"
        return True


    def consume(self, approval_id, tool_name, arguments):
        """Use an approved request exactly once."""

        request = self.requests.get(approval_id)

        if request is None or request.status != "APPROVED":
            return False

        if request.tool_name != tool_name:
            return False

        if request.arguments != arguments:
            return False

        request.status = "CONSUMED"
        return True
