import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class GuardianEmailRecipientTest(unittest.TestCase):
    def test_resolves_primary_guardian_email(self):
        from backend.notification_recipients import resolve_guardian_email_receiver

        contacts = [
            SimpleNamespace(name="Friend", email="friend@example.com", is_guardian=False),
            SimpleNamespace(name="Guardian", email="guardian@example.com", is_guardian=True),
        ]

        self.assertEqual(resolve_guardian_email_receiver(contacts), "guardian@example.com")

    def test_returns_empty_when_guardian_has_no_email(self):
        from backend.notification_recipients import resolve_guardian_email_receiver

        contacts = [
            SimpleNamespace(name="Guardian", email="", is_guardian=True),
            SimpleNamespace(name="Friend", email="friend@example.com", is_guardian=False),
        ]

        self.assertEqual(resolve_guardian_email_receiver(contacts), "")


if __name__ == "__main__":
    unittest.main()
