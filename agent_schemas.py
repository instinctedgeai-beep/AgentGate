
"""Tool definitions exposed to NVIDIA Nemotron."""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search synthetic company documents by topic or keywords. "
                "Use only for document or knowledge-base questions. "
                "Do not use to retrieve customer records."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": (
                "Retrieve a fictional customer record using its customer ID. "
                "Use for customer record lookups, not document searches. "
                "This action requires human approval and cannot run automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                },
                "required": ["customer_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_email",
            "description": "Create a draft email without sending it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["recipient", "subject", "body"],
                "additionalProperties": False,
            },
        },
    },
]
