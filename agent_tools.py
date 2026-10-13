
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
    """Search synthetic documents using keywords and safe redaction."""

    import re

    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    stopwords = {
        "the", "a", "an", "and", "or", "for", "of",
        "in", "on", "to", "about", "find", "show",
        "me", "what", "is", "please", "summarize",
    }
    terms -= stopwords

    matches = []

    for doc_id, document in DOCUMENTS.items():
        searchable = (
            doc_id + " " +
            document["title"] + " " +
            document["content"]
        ).lower()

        if not terms or not any(
            term in searchable for term in terms
        ):
            continue

        if document["classification"] != "PUBLIC":
            matches.append({
                "id": doc_id,
                "title": "[Restricted document]",
                "classification": "RESTRICTED",
                "status": "ACCESS_DENIED",
            })
            continue

        matches.append({
            "id": doc_id,
            **document,
        })

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
