"""Pydantic request/response models for the REST API."""

from datetime import date, datetime

from pydantic import BaseModel


# Dashboard
class DashboardMember(BaseModel):
    name: str
    facts_count: int
    last_active: datetime | None = None


class DashboardResponse(BaseModel):
    current_time: datetime
    members: list[DashboardMember] = []
    upcoming_reminders: list[str] = []
    recent_interactions: list[str] = []


# Calendar
class CalendarEvent(BaseModel):
    date: date
    title: str
    member: str | None = None
    event_type: str = "event"  # "event" | "birthday" | "reminder"


class CalendarResponse(BaseModel):
    month: str  # YYYY-MM
    events: list[CalendarEvent] = []


# Memory
class MemoryResponse(BaseModel):
    person: str
    facts: list[str] = []
    preferences: dict[str, str] = {}
    last_updated: datetime | None = None


class MemoryUpdateRequest(BaseModel):
    facts: list[str]


class RecallResponse(BaseModel):
    query: str
    results: list[str] = []


# Contacts
class ContactSummary(BaseModel):
    id: str
    name: str
    relationship: str
    last_contact: datetime | None = None


class ContactListResponse(BaseModel):
    contacts: list[ContactSummary] = []


# Plugins
class PluginInfo(BaseModel):
    name: str
    description: str
    plugin_type: str  # "python" | "skill" | "mcp"
    enabled: bool = True


class PluginListResponse(BaseModel):
    plugins: list[PluginInfo] = []


class MarketplaceEntry(BaseModel):
    name: str
    plugin_type: str
    version: str
    description: str


class MarketplaceResponse(BaseModel):
    plugins: list[MarketplaceEntry] = []


class PluginInstallRequest(BaseModel):
    name: str
    plugin_type: str
