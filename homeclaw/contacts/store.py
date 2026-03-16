"""Contact JSON store — one file per contact in workspaces/household/contacts/."""

from pathlib import Path

from homeclaw.contacts.models import Contact


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


def get_contact(workspaces: Path, contact_id: str) -> Contact | None:
    # Exact match first
    path = _contacts_dir(workspaces) / f"{contact_id}.json"
    if path.exists():
        return Contact.model_validate_json(path.read_text())
    # Fuzzy fallback: match by ID substring or case-insensitive name
    query = contact_id.lower()
    for contact in list_contacts(workspaces):
        if query in contact.id.lower() or query in contact.name.lower():
            return contact
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
