"""Tests for Pydantic data models."""

from datetime import date, datetime, timezone

from homeclaw.contacts.models import Contact, ContactReminder, Interaction


def test_contact_minimal():
    """Contact can be created with just required fields."""
    c = Contact(id="test", name="Test Person", relationship="friend")
    assert c.id == "test"
    assert c.interactions == []


def test_contact_full():
    """Contact with all fields populated."""
    c = Contact(
        id="jane",
        name="Jane Doe",
        relationship="family",
        birthday=date(1990, 5, 15),
        interactions=[
            Interaction(
                date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                type="call",
                notes="Caught up about work",
            )
        ],
        reminders=[
            ContactReminder(interval_days=14, next_date=date(2026, 3, 20), note="Check in")
        ],
    )
    assert c.birthday == date(1990, 5, 15)
    assert len(c.interactions) == 1
    assert c.last_contact == datetime(2026, 3, 1, tzinfo=timezone.utc)
