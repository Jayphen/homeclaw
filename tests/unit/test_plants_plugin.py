"""Tests for the plants reference plugin."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import Plugin as PluginProtocol

# Import from the source location (plugins/plants/) not workspaces
import importlib.util
import sys

_PLUGIN_FILE = Path(__file__).parent.parent.parent / "plugins" / "plants" / "plugin.py"


def _load_plants_module():  # type: ignore[no-untyped-def]
    """Import the plants plugin module from the repo source."""
    spec = importlib.util.spec_from_file_location("plants_plugin", _PLUGIN_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["plants_plugin"] = mod
    spec.loader.exec_module(mod)
    return mod


plants_mod = _load_plants_module()
PlantsPlugin = plants_mod.Plugin
Plant = plants_mod.Plant
PlantStore = plants_mod.PlantStore
get_overdue_plants = plants_mod.get_overdue_plants


def _make_plugin(tmp_path: Path) -> Any:
    """Create a Plugin instance pointing at a temp data dir."""
    return PlantsPlugin(data_dir=tmp_path)


class TestProtocolConformance:
    def test_satisfies_plugin_protocol(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        assert isinstance(plugin, PluginProtocol)

    def test_has_name_and_description(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        assert plugin.name == "plants"
        assert "watering" in plugin.description.lower()

    def test_tools_returns_tool_definitions(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        tools = plugin.tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"plant_log", "plant_status"}
        for t in tools:
            assert isinstance(t, ToolDefinition)

    def test_routines_returns_nightly_check(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        routines = plugin.routines()
        assert len(routines) == 1
        assert routines[0].cron == "0 20 * * *"
        assert "overdue" in routines[0].description.lower()


class TestPlantLog:
    @pytest.mark.asyncio
    async def test_log_creates_new_plant(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        result = await plugin.handle_tool("plant_log", {"name": "Monstera"})
        assert result["status"] == "created_and_watered"
        assert result["name"] == "Monstera"
        assert "id" in result

    @pytest.mark.asyncio
    async def test_log_waters_existing_plant(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        await plugin.handle_tool("plant_log", {"name": "Basil"})
        result = await plugin.handle_tool("plant_log", {"name": "Basil"})
        assert result["status"] == "watered"
        assert result["name"] == "Basil"

    @pytest.mark.asyncio
    async def test_log_case_insensitive_match(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        await plugin.handle_tool("plant_log", {"name": "Fern"})
        result = await plugin.handle_tool("plant_log", {"name": "fern"})
        assert result["status"] == "watered"

    @pytest.mark.asyncio
    async def test_log_with_all_fields(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        result = await plugin.handle_tool(
            "plant_log",
            {
                "name": "Orchid",
                "location": "bedroom window",
                "water_interval_days": 10,
                "notes": "mist the leaves",
            },
        )
        assert result["status"] == "created_and_watered"

        # Verify stored data
        status = await plugin.handle_tool("plant_status", {})
        plant = status["plants"][0]
        assert plant["location"] == "bedroom window"
        assert plant["water_interval_days"] == 10
        assert plant["notes"] == "mist the leaves"

    @pytest.mark.asyncio
    async def test_log_updates_fields_on_existing(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        await plugin.handle_tool(
            "plant_log", {"name": "Cactus", "location": "desk"}
        )
        await plugin.handle_tool(
            "plant_log", {"name": "Cactus", "location": "shelf", "water_interval_days": 14}
        )

        status = await plugin.handle_tool("plant_status", {})
        plant = status["plants"][0]
        assert plant["location"] == "shelf"
        assert plant["water_interval_days"] == 14

    @pytest.mark.asyncio
    async def test_persists_to_disk(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        await plugin.handle_tool("plant_log", {"name": "Snake Plant"})

        data_file = tmp_path / "plants.json"
        assert data_file.exists()
        data = json.loads(data_file.read_text())
        assert len(data["plants"]) == 1
        assert data["plants"][0]["name"] == "Snake Plant"


class TestPlantStatus:
    @pytest.mark.asyncio
    async def test_empty_returns_zero_count(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        result = await plugin.handle_tool("plant_status", {})
        assert result["count"] == 0
        assert result["plants"] == []

    @pytest.mark.asyncio
    async def test_returns_all_plants(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        await plugin.handle_tool("plant_log", {"name": "A"})
        await plugin.handle_tool("plant_log", {"name": "B"})
        await plugin.handle_tool("plant_log", {"name": "C"})

        result = await plugin.handle_tool("plant_status", {})
        assert result["count"] == 3
        names = {p["name"] for p in result["plants"]}
        assert names == {"A", "B", "C"}

    @pytest.mark.asyncio
    async def test_shows_overdue_status(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        await plugin.handle_tool(
            "plant_log", {"name": "Thirsty", "water_interval_days": 1}
        )

        # Manually backdate the last_watered to make it overdue
        store_data = json.loads((tmp_path / "plants.json").read_text())
        store_data["plants"][0]["last_watered"] = "2020-01-01T00:00:00+00:00"
        (tmp_path / "plants.json").write_text(json.dumps(store_data))

        result = await plugin.handle_tool("plant_status", {})
        plant = result["plants"][0]
        assert plant["overdue"] is True
        assert plant["days_since_watered"] > 1

    @pytest.mark.asyncio
    async def test_recently_watered_not_overdue(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        await plugin.handle_tool(
            "plant_log", {"name": "Happy", "water_interval_days": 30}
        )

        result = await plugin.handle_tool("plant_status", {})
        plant = result["plants"][0]
        assert plant["overdue"] is False
        assert plant["days_since_watered"] == 0


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, tmp_path: Path) -> None:
        plugin = _make_plugin(tmp_path)
        result = await plugin.handle_tool("nonexistent", {})
        assert "error" in result


class TestGetOverduePlants:
    def test_no_plants_returns_empty(self, tmp_path: Path) -> None:
        result = get_overdue_plants(data_dir=tmp_path)
        assert result == []

    def test_overdue_plant_returned(self, tmp_path: Path) -> None:
        store = PlantStore(
            plants=[
                Plant(
                    id="abc",
                    name="Dry",
                    water_interval_days=1,
                    last_watered="2020-01-01T00:00:00+00:00",
                )
            ]
        )
        (tmp_path / "plants.json").write_text(store.model_dump_json())

        result = get_overdue_plants(data_dir=tmp_path)
        assert len(result) == 1
        assert result[0].name == "Dry"

    def test_never_watered_is_overdue(self, tmp_path: Path) -> None:
        store = PlantStore(
            plants=[Plant(id="xyz", name="Neglected", last_watered=None)]
        )
        (tmp_path / "plants.json").write_text(store.model_dump_json())

        result = get_overdue_plants(data_dir=tmp_path)
        assert len(result) == 1
