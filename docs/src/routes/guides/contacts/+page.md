<svelte:head>
  <title>Contacts — homeclaw docs</title>
</svelte:head>

# Contacts

homeclaw includes a full contact management system — think of it as a household CRM for the people in your lives.

## Features

- **Interactions** — log when you last spoke to someone, with notes
- **Reminders** — set follow-up reminders for contacts ("check in with Mom next week")
- **Per-person private notes** — each household member can add private notes to shared contacts
- **Categories and tags** — organize contacts however makes sense for your household
- **Search** — full-text search across all contact fields

## Storage

Contacts are stored as JSON in the workspaces directory and searched via dedicated tools (`contact_search`). Per-contact notes are stored as markdown and are indexed by memsearch for semantic recall.

## Tools

The agent has built-in tools for contact management:

- `contact_add` — create a new contact
- `contact_update` — update contact fields
- `contact_search` — search contacts
- `contact_interaction` — log an interaction
- `contact_reminder` — set a reminder for a contact
