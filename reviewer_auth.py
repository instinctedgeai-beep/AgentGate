
"""Local reviewer authentication for AgentGate."""

import os
import secrets
import time


class ReviewerAuth:
    def __init__(self, reviewer_id=None, reviewer_secret=None, session_seconds=900):
        self.reviewer_id = reviewer_id or os.getenv("AGENTGATE_REVIEWER_ID")
        self.reviewer_secret = reviewer_secret or os.getenv("AGENTGATE_REVIEWER_SECRET")
        self.session_seconds = session_seconds
        self.sessions = {}

    def login(self, secret):
        if not self.reviewer_id or not self.reviewer_secret:
            return None

        if not isinstance(secret, str):
            return None

        if not secrets.compare_digest(secret, self.reviewer_secret):
            return None

        token = secrets.token_urlsafe(32)
        self.sessions[token] = (self.reviewer_id, time.monotonic() + self.session_seconds)
        return token

    def authenticate(self, token):
        if not isinstance(token, str) or not token:
            return None

        session = self.sessions.get(token)
        if session is None:
            return None

        reviewer_id, expires_at = session
        if time.monotonic() >= expires_at:
            self.sessions.pop(token, None)
            return None

        return reviewer_id

    def logout(self, token):
        return self.sessions.pop(token, None) is not None
