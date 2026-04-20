from typing import Iterable, Any


def resolve_guardian_email_receiver(contacts: Iterable[Any]) -> str:
    """Return the primary guardian email, or empty string when unavailable."""
    for contact in contacts:
        if not bool(getattr(contact, "is_guardian", False)):
            continue
        email = str(getattr(contact, "email", "") or "").strip()
        if "@" in email:
            return email
        return ""
    return ""
