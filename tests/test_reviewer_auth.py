
import unittest

from reviewer_auth import ReviewerAuth


class ReviewerAuthTests(unittest.TestCase):
    def setUp(self):
        self.auth = ReviewerAuth(
            reviewer_id="test-reviewer",
            reviewer_secret="test-secret",
        )

    def test_correct_secret_creates_session(self):
        token = self.auth.login("test-secret")
        self.assertIsNotNone(token)
        self.assertEqual(self.auth.authenticate(token), "test-reviewer")

    def test_wrong_secret_is_rejected(self):
        self.assertIsNone(self.auth.login("wrong-secret"))

    def test_missing_token_is_rejected(self):
        self.assertIsNone(self.auth.authenticate(None))

    def test_logout_invalidates_session(self):
        token = self.auth.login("test-secret")
        self.assertTrue(self.auth.logout(token))
        self.assertIsNone(self.auth.authenticate(token))

    def test_expired_session_is_rejected(self):
        auth = ReviewerAuth(
            reviewer_id="test-reviewer",
            reviewer_secret="test-secret",
            session_seconds=-1,
        )
        token = auth.login("test-secret")
        self.assertIsNone(auth.authenticate(token))

    def test_unconfigured_reviewer_cannot_login(self):
        auth = ReviewerAuth(reviewer_id="", reviewer_secret="")
        auth.reviewer_id = None
        auth.reviewer_secret = None
        self.assertIsNone(auth.login("anything"))


if __name__ == "__main__":
    unittest.main()
