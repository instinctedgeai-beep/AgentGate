
import unittest
from unittest.mock import patch

from reviewer_auth import ReviewerAuth


class DeletionCodeTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(
            "os.environ",
            {"AGENTGATE_DELETION_CODE": "042681"},
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

        self.auth = ReviewerAuth(
            reviewer_id="test-reviewer",
            reviewer_secret="test-login-secret",
        )
        self.token = self.auth.login("test-login-secret")
        self.assertIsNotNone(self.token)

    def test_correct_code_requires_authenticated_session(self):
        self.assertEqual(
            self.auth.verify_deletion_code(self.token, "042681"),
            "test-reviewer",
        )
        self.assertIsNone(
            self.auth.verify_deletion_code("invalid-session", "042681")
        )

    def test_wrong_code_is_rejected_without_revoking_session(self):
        self.assertIsNone(
            self.auth.verify_deletion_code(self.token, "123456")
        )
        self.assertEqual(
            self.auth.authenticate(self.token),
            "test-reviewer",
        )

    def test_code_requires_exactly_six_digits(self):
        for invalid_code in (
            "42681",
            "0042681",
            "abcdef",
            "04268a",
            "",
            None,
            42681,
        ):
            with self.subTest(code=invalid_code):
                self.assertIsNone(
                    self.auth.verify_deletion_code(
                        self.token, invalid_code
                    )
                )

    def test_five_wrong_codes_trigger_lockout(self):
        for _ in range(5):
            self.assertIsNone(
                self.auth.verify_deletion_code(self.token, "999999")
            )

        self.assertIsNone(
            self.auth.verify_deletion_code(self.token, "042681")
        )
        self.assertEqual(
            self.auth.authenticate(self.token),
            "test-reviewer",
        )

    def test_missing_code_configuration_fails_closed(self):
        self.auth.deletion_code = None

        self.assertIsNone(
            self.auth.verify_deletion_code(self.token, "042681")
        )


if __name__ == "__main__":
    unittest.main()
