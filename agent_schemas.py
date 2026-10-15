
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
                "Request a customer record lookup using a trusted local identifier. "
                "When a customer lookup is requested, set customer_id to exactly "
                "'TRUSTED_CUSTOMER'. Never invent or supply an actual customer ID. "
                "The trusted backend resolves this placeholder after validating it. "
                "Human approval is required before execution."
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
