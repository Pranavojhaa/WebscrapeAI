import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from account_store import AccountStore, AccountStoreError


class AccountStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = AccountStore("sqlite:///:memory:")
        self.store.initialize("owner@example.test", "owner-test-password-long-enough")

    def test_bootstraps_admin_and_checks_password(self):
        user = self.store.authenticate("OWNER@example.test", "owner-test-password-long-enough")

        self.assertIsNotNone(user)
        self.assertTrue(user["is_admin"])
        self.assertIsNone(self.store.authenticate("owner@example.test", "wrong-password"))

    def test_admin_can_create_and_disable_an_approved_user(self):
        self.store.create_user("member@example.test", "member-test-password-long-enough")
        self.assertIsNotNone(
            self.store.authenticate("member@example.test", "member-test-password-long-enough")
        )

        self.store.set_active("member@example.test", False, "owner@example.test")

        self.assertIsNone(
            self.store.authenticate("member@example.test", "member-test-password-long-enough")
        )
        self.assertFalse(self.store.get_user("member@example.test")["is_active"])

    def test_migrates_an_existing_users_table(self):
        legacy = AccountStore("sqlite:///:memory:")
        with legacy._connection() as connection:
            connection.execute(
                """CREATE TABLE users (
                    email TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            from werkzeug.security import generate_password_hash

            connection.execute(
                "INSERT INTO users (email, password_hash, is_admin, is_active) VALUES (?, ?, ?, ?)",
                ("owner@example.test", generate_password_hash("owner-password-long-enough-for-test"), True, True),
            )

        legacy.initialize()

        self.assertEqual(legacy.get_user("owner@example.test")["session_version"], 0)
        self.assertTrue(
            legacy.issue_password_reset(
                "owner@example.test", "legacy-schema-reset-hash", datetime.now(timezone.utc) + timedelta(minutes=30)
            )
        )

    def test_cannot_disable_last_active_admin_or_self(self):
        with self.assertRaises(AccountStoreError):
            self.store.set_active("owner@example.test", False, "owner@example.test")

        self.store.create_user("second-admin@example.test", "second-admin-password-long-enough")
        with self.store._connection() as connection:
            connection.execute("UPDATE users SET is_admin = TRUE WHERE email = ?", ("second-admin@example.test",))
        self.store.set_active("owner@example.test", False, "second-admin@example.test")

        self.assertFalse(self.store.get_user("owner@example.test")["is_active"])

    def test_first_admin_requires_a_long_bootstrap_password(self):
        uninitialized = AccountStore("sqlite:///:memory:")

        with self.assertRaises(AccountStoreError):
            uninitialized.initialize("owner@example.test", "short")

    def test_password_reset_token_is_single_use_and_revokes_sessions(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(
            self.store.issue_password_reset(
                "owner@example.test", "hashed-reset-token", now + timedelta(minutes=30)
            )
        )

        self.assertTrue(
            self.store.consume_password_reset(
                "hashed-reset-token", "a-new-password-with-at-least-16-chars", now
            )
        )
        self.assertIsNotNone(
            self.store.authenticate("owner@example.test", "a-new-password-with-at-least-16-chars")
        )
        self.assertIsNone(
            self.store.authenticate("owner@example.test", "owner-test-password-long-enough")
        )
        self.assertEqual(self.store.get_user("owner@example.test")["session_version"], 1)
        self.assertFalse(
            self.store.consume_password_reset(
                "hashed-reset-token", "another-new-password-with-16-chars", now
            )
        )

    def test_password_reset_rejects_wrong_and_expired_tokens(self):
        now = datetime.now(timezone.utc)
        self.store.issue_password_reset(
            "owner@example.test", "expired-token-hash", now - timedelta(seconds=1)
        )
        self.assertFalse(
            self.store.consume_password_reset(
                "wrong-token-hash", "a-new-password-with-at-least-16-chars", now
            )
        )
        self.assertFalse(
            self.store.consume_password_reset(
                "expired-token-hash", "a-new-password-with-at-least-16-chars", now
            )
        )
        self.assertIsNotNone(
            self.store.authenticate("owner@example.test", "owner-test-password-long-enough")
        )

    def test_new_reset_request_invalidates_the_previous_link(self):
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        self.store.issue_password_reset("owner@example.test", "first-token-hash", expires_at)
        self.store.issue_password_reset("owner@example.test", "second-token-hash", expires_at)

        self.assertFalse(
            self.store.consume_password_reset(
                "first-token-hash", "a-new-password-with-at-least-16-chars"
            )
        )
        self.assertTrue(
            self.store.consume_password_reset(
                "second-token-hash", "a-new-password-with-at-least-16-chars"
            )
        )

    def test_password_reset_rejects_weak_passwords(self):
        now = datetime.now(timezone.utc)
        self.store.issue_password_reset(
            "owner@example.test", "valid-token-hash", now + timedelta(minutes=30)
        )
        with self.assertRaises(AccountStoreError):
            self.store.consume_password_reset("valid-token-hash", "too-short", now)
        self.assertTrue(
            self.store.consume_password_reset(
                "valid-token-hash", "a-new-password-with-at-least-16-chars", now
            )
        )


if __name__ == "__main__":
    unittest.main()
