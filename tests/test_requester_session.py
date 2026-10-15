
import unittest

from requester_session import RequesterSession


class RequesterSessionTests(unittest.TestCase):

    def setUp(self):
        self.sessions = RequesterSession(ttl_seconds=900)

    def test_session_creation(self):
        token = self.sessions.create("test-agent")
        self.assertIsInstance(token, str)
        self.assertEqual(
            self.sessions.authenticate(token),
            "test-agent",
        )

    def test_tokens_are_unique(self):
        first = self.sessions.create("test-agent")
        second = self.sessions.create("test-agent")
        self.assertNotEqual(first, second)

    def test_unknown_token_rejected(self):
        self.assertIsNone(
            self.sessions.authenticate("invalid-token")
        )

    def test_revoked_session_rejected(self):
        token = self.sessions.create("test-agent")
        self.assertTrue(self.sessions.revoke(token))
        self.assertIsNone(self.sessions.authenticate(token))

    def test_invalid_identity_rejected(self):
        self.assertIsNone(self.sessions.create(""))
        self.assertIsNone(self.sessions.create(None))


if __name__ == "__main__":
    unittest.main()
