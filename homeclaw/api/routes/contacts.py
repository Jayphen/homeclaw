"""Contacts API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homeclaw.api.deps import AuthDep, MemberDep, get_config
from homeclaw.contacts.models import Contact
from homeclaw.contacts.store import get_contact, list_contacts, save_contact_safe

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


class ContactUpdate(BaseModel):
    name: str | None = None
    nicknames: list[str] | None = None
    relationship: str | None = None


def _notes_for(workspaces: Any, contact_id: str) -> str | None:
    """Read the household-level markdown notes file for a contact."""
    path = workspaces / "household" / "contacts" / "notes" / f"{contact_id}.md"
    if not path.is_file():
        return None
    return path.read_text()


def _personal_notes_for(workspaces: Any, member: str | None, contact_id: str) -> str | None:
    """Read per-person private notes for a contact."""
    if not member:
        return None
    path = workspaces / member / "contacts" / "notes" / f"{contact_id}.md"
    if not path.is_file():
        return None
    return path.read_text()


@router.get("", dependencies=[AuthDep])
async def contacts_list() -> list[dict[str, Any]]:
    workspaces = get_config().workspaces.resolve()
    contacts = list_contacts(workspaces)
    return [
        {
            "id": c.id,
            "name": c.name,
            "nicknames": c.nicknames,
            "relationship": c.relationship,
            "birthday": c.birthday.isoformat() if c.birthday else None,
            "last_contact": c.last_contact.isoformat() if c.last_contact else None,
            "reminder_count": len(c.reminders),
            "member": c.member,
        }
        for c in contacts
    ]


@router.get("/{contact_id}")
async def contacts_detail(
    contact_id: str,
    member: Annotated[str | None, MemberDep],
) -> dict[str, Any]:
    workspaces = get_config().workspaces.resolve()
    contact = get_contact(workspaces, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail=f"Contact '{contact_id}' not found")
    data = contact.model_dump(mode="json")
    data["notes_md"] = _notes_for(workspaces, contact.id)
    data["personal_notes_md"] = _personal_notes_for(workspaces, member, contact.id)
    return data


@router.put("/{contact_id}", dependencies=[AuthDep])
async def contacts_update(contact_id: str, body: ContactUpdate) -> dict[str, Any]:
    workspaces = get_config().workspaces.resolve()
    contact = get_contact(workspaces, contact_id)
    if not contact:
        contact = Contact(
            id=contact_id,
            name=body.name or contact_id,
            relationship=body.relationship or "other",
        )

    if body.name is not None:
        contact.name = body.name
    if body.nicknames is not None:
        contact.nicknames = body.nicknames
    if body.relationship is not None:
        contact.relationship = body.relationship

    await save_contact_safe(workspaces, contact)
    return {"status": "updated", "id": contact.id}
