"""Contact JSON store — one file per contact in workspaces/household/contacts/."""

from difflib import SequenceMatcher
from pathlib import Path

from homeclaw.contacts.models import Contact

_FUZZY_THRESHOLD = 0.4


def _contacts_dir(workspaces: Path) -> Path:
    d = workspaces / "household" / "contacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_contacts(workspaces: Path) -> list[Contact]:
    contacts_dir = _contacts_dir(workspaces)
    contacts: list[Contact] = []
    for path in sorted(contacts_dir.glob("*.json")):
        contacts.append(Contact.model_validate_json(path.read_text()))
    return contacts


def _match_score(query: str, contact: Contact) -> float:
    """Score how well a query matches a contact (0.0–1.0).

    Checks against the contact ID, full name, first name, and individual
    name parts. Handles nicknames, prefixes, and typos via SequenceMatcher.
    """
    query = query.lower().strip()
    candidates = [
        contact.id.lower(),
        contact.name.lower(),
    ]
    # Add individual name parts (first name, last name, etc.)
    candidates.extend(part.lower() for part in contact.name.split())
    # Add ID parts split by hyphens (e.g. "grandma" from "grandma-eleanor")
    candidates.extend(part.lower() for part in contact.id.split("-"))

    best = 0.0
    for candidate in candidates:
        # Exact match
        if query == candidate:
            return 1.0
        # Prefix match ("sar" -> "sarah", "gran" -> "grandma")
        if candidate.startswith(query):
            best = max(best, 0.8 + 0.2 * (len(query) / len(candidate)))
        # Substring match
        elif query in candidate:
            best = max(best, 0.7)
        # Fuzzy similarity (handles typos)
        ratio = SequenceMatcher(None, query, candidate).ratio()
        best = max(best, ratio)

    return best


def get_contact(workspaces: Path, contact_id: str) -> Contact | None:
    # Exact file match first
    path = _contacts_dir(workspaces) / f"{contact_id}.json"
    if path.exists():
        return Contact.model_validate_json(path.read_text())
    # Fuzzy match: score all contacts and return the best above threshold
    contacts = list_contacts(workspaces)
    if not contacts:
        return None
    scored = [(c, _match_score(contact_id, c)) for c in contacts]
    scored.sort(key=lambda x: x[1], reverse=True)
    best_contact, best_score = scored[0]
    if best_score >= _FUZZY_THRESHOLD:
        return best_contact
    return None


def save_contact(workspaces: Path, contact: Contact) -> None:
    path = _contacts_dir(workspaces) / f"{contact.id}.json"
    path.write_text(contact.model_dump_json(indent=2))


def delete_contact(workspaces: Path, contact_id: str) -> bool:
    path = _contacts_dir(workspaces) / f"{contact_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True
