"""Tests for per-turn additional context rendering."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from homeclaw.agent.additional_context import (
    AdditionalContext,
    append_additional_context_to_text,
    build_additional_context,
    strip_additional_context,
)


def test_empty_envelope_is_omitted() -> None:
    context = AdditionalContext()

    assert context.render() == ""
    assert append_additional_context_to_text("hello", context) == "hello"


def test_partial_fields_render_only_present_tags() -> None:
    rendered = AdditionalContext(channel="telegram_group", sender="alice").render()

    assert rendered.startswith("<additional_context>")
    assert "<channel>\ntelegram_group\n</channel>" in rendered
    assert "<sender>\nalice\n</sender>" in rendered
    assert "<skills_available>" not in rendered
    assert "<memory_facts>" not in rendered


def test_strip_round_trips_user_visible_text() -> None:
    visible = "Remember to buy milk"
    with_context = append_additional_context_to_text(
        visible,
        AdditionalContext(current_time_zone="Australia/Sydney"),
    )

    assert strip_additional_context(with_context) == visible


def test_build_context_includes_recent_routine_runtime_state(tmp_path: Path) -> None:
    household = tmp_path / "household"
    household.mkdir()
    now = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    (tmp_path / "config.json").write_text(
        json.dumps({"timezone": "Australia/Sydney"}),
    )
    (household / ".routine_last_run.json").write_text(
        json.dumps(
            {
                "routine:morning-brief": (now - timedelta(hours=1)).isoformat(),
                "routine:old-news": (now - timedelta(hours=8)).isoformat(),
            }
        ),
    )

    context = build_additional_context(
        workspaces=tmp_path,
        person="Alice",
        channel_label="web",
        include_sender=True,
        now=now,
    )
    rendered = context.render()

    assert "<current_time_zone>\nAustralia/Sydney\n</current_time_zone>" in rendered
    assert "<channel>\nweb\n</channel>" in rendered
    assert "<sender>\nalice\n</sender>" in rendered
    assert "Morning brief" in rendered
    assert "Old news" not in rendered
    assert "<skills_available>" not in rendered
    assert "<memory_facts>" not in rendered
    assert "<active_reminders>" not in rendered
