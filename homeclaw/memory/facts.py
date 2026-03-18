"""Structured facts store (Layer 1) — always on, injected in full into every context."""

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from homeclaw.locking import LockPool


class HouseholdMemory(BaseModel):
    facts: list[str] = []
    preferences: dict[str, str | list[str]] = {}
    last_updated: datetime | None = None


_lock_pool = LockPool()


def load_memory(workspaces: Path, person: str) -> HouseholdMemory:
    path = workspaces / person / "memory.json"
    if not path.exists():
        return HouseholdMemory()
    return HouseholdMemory.model_validate_json(path.read_text())


def save_memory(workspaces: Path, person: str, memory: HouseholdMemory) -> None:
    person_dir = workspaces / person
    person_dir.mkdir(parents=True, exist_ok=True)
    memory.last_updated = datetime.now(timezone.utc)
    (person_dir / "memory.json").write_text(memory.model_dump_json(indent=2))


async def save_memory_safe(workspaces: Path, person: str, memory: HouseholdMemory) -> None:
    """Save memory with per-person locking to prevent concurrent races."""
    async with _lock_pool.lock_for(person):
        save_memory(workspaces, person, memory)
