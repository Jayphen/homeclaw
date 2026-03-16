"""Plants plugin — track plant watering schedules.

Reference implementation of the homeclaw Plugin Protocol.
Storage: workspaces/plugins/plants/plants.json
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import RoutineDefinition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class Plant(BaseModel):
    id: str
    name: str
    location: str = ""
    water_interval_days: int = 7
    last_watered: datetime | None = None
    notes: str = ""


class PlantStore(BaseModel):
    plants: list[Plant] = []


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _data_path(data_dir: Path) -> Path:
    return data_dir / "plants.json"


def _load_store(data_dir: Path) -> PlantStore:
    path = _data_path(data_dir)
    if not path.exists():
        return PlantStore()
    try:
        return PlantStore.model_validate_json(path.read_text())
    except Exception:
        logger.exception("Failed to parse plants.json, starting fresh")
        return PlantStore()


def _save_store(data_dir: Path, store: PlantStore) -> None:
    path = _data_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(store.model_dump_json(indent=2) + "\n")


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------


class Plugin:
    """Track plant watering schedules for the household."""

    name = "plants"
    description = "Track plant watering schedules and get overdue reminders"

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="plant_log",
                description="Log a watering event for a plant. Creates the plant if it doesn't exist.",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Plant name (e.g. 'monstera', 'basil')",
                        },
                        "location": {
                            "type": "string",
                            "description": "Where the plant lives (e.g. 'kitchen window')",
                        },
                        "water_interval_days": {
                            "type": "integer",
                            "description": "Days between watering (default 7)",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Optional notes (e.g. 'leaves yellowing')",
                        },
                    },
                    "required": ["name"],
                },
            ),
            ToolDefinition(
                name="plant_status",
                description="List all plants and their watering schedules, including overdue status.",
                parameters={"type": "object", "properties": {}},
            ),
        ]

    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "plant_log":
            return self._handle_plant_log(args)
        if name == "plant_status":
            return self._handle_plant_status()
        return {"error": f"Unknown tool: {name}"}

    def routines(self) -> list[RoutineDefinition]:
        return [
            RoutineDefinition(
                name="overdue_check",
                cron="0 20 * * *",
                description="Check for plants that are overdue for watering",
            )
        ]

    # --- Tool handlers ---

    def _handle_plant_log(self, args: dict[str, Any]) -> dict[str, Any]:
        store = _load_store(self._data_dir)
        plant_name: str = args["name"]
        now = datetime.now(timezone.utc)

        # Find existing plant by name (case-insensitive)
        plant = next(
            (p for p in store.plants if p.name.lower() == plant_name.lower()),
            None,
        )

        if plant is None:
            plant = Plant(
                id=uuid4().hex[:8],
                name=plant_name,
                location=args.get("location", ""),
                water_interval_days=args.get("water_interval_days", 7),
                notes=args.get("notes", ""),
                last_watered=now,
            )
            store.plants.append(plant)
            _save_store(self._data_dir, store)
            return {
                "status": "created_and_watered",
                "id": plant.id,
                "name": plant.name,
                "next_water": _next_water_str(plant),
            }

        # Update existing plant
        plant.last_watered = now
        if "location" in args:
            plant.location = args["location"]
        if "water_interval_days" in args:
            plant.water_interval_days = args["water_interval_days"]
        if "notes" in args:
            plant.notes = args["notes"]

        _save_store(self._data_dir, store)
        return {
            "status": "watered",
            "id": plant.id,
            "name": plant.name,
            "next_water": _next_water_str(plant),
        }

    def _handle_plant_status(self) -> dict[str, Any]:
        store = _load_store(self._data_dir)
        now = datetime.now(timezone.utc)

        plants_out: list[dict[str, Any]] = []
        for p in store.plants:
            entry: dict[str, Any] = {
                "id": p.id,
                "name": p.name,
                "location": p.location,
                "water_interval_days": p.water_interval_days,
                "last_watered": p.last_watered.isoformat() if p.last_watered else None,
                "notes": p.notes,
            }
            if p.last_watered:
                days_since = (now - p.last_watered).days
                entry["days_since_watered"] = days_since
                entry["overdue"] = days_since >= p.water_interval_days
                entry["next_water"] = _next_water_str(p)
            else:
                entry["days_since_watered"] = None
                entry["overdue"] = True
                entry["next_water"] = "now"
            plants_out.append(entry)

        return {"plants": plants_out, "count": len(plants_out)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_water_str(plant: Plant) -> str:
    """Human-readable next-watering date."""
    if plant.last_watered is None:
        return "now"
    from datetime import timedelta

    next_dt = plant.last_watered + timedelta(days=plant.water_interval_days)
    return next_dt.strftime("%Y-%m-%d")


def get_overdue_plants(data_dir: Path) -> list[Plant]:
    """Return plants that are overdue for watering. Used by the nightly routine."""
    store = _load_store(data_dir)
    now = datetime.now(timezone.utc)
    overdue: list[Plant] = []
    for p in store.plants:
        if p.last_watered is None:
            overdue.append(p)
        elif (now - p.last_watered).days >= p.water_interval_days:
            overdue.append(p)
    return overdue
