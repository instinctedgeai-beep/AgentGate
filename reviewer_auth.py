
"""Local reviewer authentication for AgentGate."""

import os
import secrets
import threading
import time


class ReviewerAuth:
    def __init__(
        self,
        reviewer_id=None,
        reviewer_secret=None,
        session_seconds=900,
        max_attempts=5,
        lockout_seconds=60,
    ):
        self.reviewer_id = (
            reviewer_id if reviewer_id is not None
            else os.getenv("AGENTGATE_REVIEWER_ID")
        )
        self.reviewer_secret = (
            reviewer_secret if reviewer_secret is not None
            else os.getenv("AGENTGATE_REVIEWER_SECRET")
        )

        self.session_seconds = session_seconds
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds

        self.sessions = {}
        self.failed_attempts = []
        self.locked_until = 0
        self.lock = threading.RLock()

    def login(self, secret):
        with self.lock:
            now = time.monotonic()

            if now < self.locked_until:
                return None

            if not self.reviewer_id or not self.reviewer_secret:
                return None

            self.failed_attempts = [
                attempt for attempt in self.failed_attempts
                if now - attempt < self.lockout_seconds
            ]

            valid = (
                isinstance(secret, str)
                and secrets.compare_digest(
                    secret,
                    self.reviewer_secret,
                )
            )

            if not valid:
                self.failed_attempts.append(now)

                if len(self.failed_attempts) >= self.max_attempts:
                    self.locked_until = now + self.lockout_seconds
                    self.failed_attempts.clear()

                return None

            self.failed_attempts.clear()

            token = secrets.token_urlsafe(32)
            self.sessions[token] = (
                self.reviewer_id,
                now + self.session_seconds,
            )

            return token

    def authenticate(self, token):
        if not isinstance(token, str) or not token:
            return None

        with self.lock:
            session = self.sessions.get(token)

            if session is None:
                return None

            reviewer_id, expires_at = session

            if time.monotonic() >= expires_at:
                self.sessions.pop(token, None)
                return None

            return reviewer_id

    def logout(self, token):
        with self.lock:
            return self.sessions.pop(token, None) is not None
