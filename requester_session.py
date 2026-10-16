
"""Short-lived requester sessions for the local AgentGate demo."""

import secrets
import threading
import time


class RequesterSession:
    def __init__(self, ttl_seconds=900):
        self.ttl_seconds = ttl_seconds
        self.sessions = {}
        self.lock = threading.RLock()

    def create(self, requester_id):
        if not isinstance(requester_id, str) or not requester_id:
            return None

        token = secrets.token_urlsafe(32)

        with self.lock:
            self.sessions[token] = (
                requester_id,
                time.monotonic() + self.ttl_seconds,
            )

        return token

    def authenticate(self, token):
        if not isinstance(token, str) or not token:
            return None

        with self.lock:
            session = self.sessions.get(token)

            if session is None:
                return None

            requester_id, expires_at = session

            if time.monotonic() >= expires_at:
                self.sessions.pop(token, None)
                return None

            return requester_id

    def revoke(self, token):
        with self.lock:
            return self.sessions.pop(token, None) is not None
