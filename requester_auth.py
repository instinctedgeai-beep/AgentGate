
"""Server-side authorization for AI tool requesters."""

import os
import secrets


class RequesterAuth:
    def __init__(
        self,
        requester_id=None,
        api_key=None,
        allowed_customers=None,
    ):
        self.requester_id = (
            requester_id
            if requester_id is not None
            else os.getenv("AGENTGATE_REQUESTER_ID")
        )

        self.api_key = (
            api_key
            if api_key is not None
            else os.getenv("AGENTGATE_REQUESTER_API_KEY")
        )

        if allowed_customers is None:
            configured = os.getenv(
                "AGENTGATE_REQUESTER_CUSTOMERS", ""
            )
            allowed_customers = configured.split(",")

        self.allowed_customers = frozenset(
            customer.strip()
            for customer in allowed_customers
            if isinstance(customer, str) and customer.strip()
        )

    def authenticate(self, presented_key):
        """Return the configured identity for a valid credential."""
        if not (
            isinstance(presented_key, str)
            and presented_key
            and self.requester_id
            and self.api_key
        ):
            return None

        if not secrets.compare_digest(
            presented_key, self.api_key
        ):
            return None

        return self.requester_id

    def authorize(self, requester_id, tool, arguments):
        """Deny access unless the requester and action are permitted."""
        if not requester_id or requester_id != self.requester_id:
            return False

        if not isinstance(arguments, dict):
            return False

        if tool == "search_documents":
            return (
                set(arguments) == {"query"}
                and isinstance(arguments["query"], str)
                and bool(arguments["query"].strip())
            )

        if tool == "lookup_customer":
            return (
                set(arguments) == {"customer_id"}
                and isinstance(arguments["customer_id"], str)
                and arguments["customer_id"] in self.allowed_customers
            )

        return False
