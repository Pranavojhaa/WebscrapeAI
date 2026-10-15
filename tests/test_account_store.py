import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
