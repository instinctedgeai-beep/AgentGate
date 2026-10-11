
"""Synthetic tools for the AgentGate AI agent."""

DOCUMENTS = {
    "product": {
        "title": "Public Product Overview",
        "content": "AgentGate monitors AI routing and policy decisions.",
        "classification": "PUBLIC",
    },
    "finance": {
        "title": "Internal Financial Forecast",
        "content": "Synthetic revenue projection: $2.4M.",
        "classification": "CONFIDENTIAL",
    },
}

CUSTOMERS = {
    "CUST-1001": {
        "name": "Alex Morgan",
        "status": "Active",
        "classification": "PRIVATE",
    }
}


def search_documents(query: str) -> dict:
    """Search fictional company documents."""
    matches = [
        {"id": doc_id, **document}
        for doc_id, document in DOCUMENTS.items()
        if query.lower() in (
            document["title"] + " " + document["content"]
        ).lower()
    ]
    return {"results": matches}


def lookup_customer(customer_id: str) -> dict:
    """Retrieve fictional customer information."""
    record = CUSTOMERS.get(customer_id)

    if record is None:
        return {"error": "Customer not found"}

    return {"customer_id": customer_id, **record}


def draft_email(recipient: str, subject: str, body: str) -> dict:
    """Prepare an email without sending it."""
    return {
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "status": "DRAFT_ONLY",
    }
