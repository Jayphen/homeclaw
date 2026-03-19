"""Unit tests for the context builder against dev fixtures."""

from datetime import datetime
from pathlib import Path

import pytest

from homeclaw.agent.context import build_context


class TestAliceContext:
    """Tests for Alice's context output."""

    async def test_no_layer1_facts_injected(self, dev_workspaces: Path) -> None:
        """Layer 1 facts are no longer injected — retrieved via tools or semantic recall."""
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "Vegetarian" not in ctx
        assert "reminder_time" not in ctx

    async def test_includes_eleanor_reminder(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "Eleanor" in ctx
        assert "Bi-weekly check-in call" in ctx

    async def test_includes_sarah_chen_reminder(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "Sarah Chen" in ctx
        assert "Monthly catch-up" in ctx


class TestBobContext:
    """Tests for Bob's context output."""

    async def test_no_cross_person_facts(self, dev_workspaces: Path) -> None:
        """Per-person facts should not leak into another person's context.

        Household-wide info (like pet names in household memory) is expected
        to appear for all members.
        """
        ctx = await build_context("hello", "bob", dev_workspaces)
        assert "Vegetarian" not in ctx
        assert "Runs on weekends" not in ctx


class TestHouseholdProfile:
    """Tests for household profile injection."""

    async def test_includes_household_profile(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "Household profile:" in ctx
        assert "[about]" in ctx
        assert "Family of four" in ctx
        assert "Mochi and Biscuit" in ctx

    async def test_household_profile_in_shared_context(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces, shared_only=True)
        assert "Household profile:" in ctx
        assert "Family of four" in ctx

    async def test_no_profile_without_household_memory(self, tmp_path: Path) -> None:
        ctx = await build_context("hello", "alice", tmp_path)
        assert "Household profile:" not in ctx


class TestRecentNotes:
    """Tests for recent notes injection."""

    async def test_includes_todays_notes(self, dev_workspaces: Path) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        notes_dir = dev_workspaces / "alice" / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        (notes_dir / f"{today}.md").write_text("- [09:00] Dentist at 3pm\n")

        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "Your recent notes:" in ctx
        assert "Dentist at 3pm" in ctx

    async def test_excludes_old_notes(self, dev_workspaces: Path) -> None:
        """Notes older than max_recent_notes_days are not injected."""
        ctx = await build_context("hello", "alice", dev_workspaces)
        # alice's only note is from 2026-03-12 — too old for the 3-day window
        assert "call Mum about Easter" not in ctx

    async def test_no_notes_in_shared_context(self, dev_workspaces: Path) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        notes_dir = dev_workspaces / "alice" / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        (notes_dir / f"{today}.md").write_text("- [09:00] Personal note\n")

        ctx = await build_context("hello", "alice", dev_workspaces, shared_only=True)
        assert "Your recent notes:" not in ctx


class TestPersonMemoryTopics:
    """Tests for person memory topic listing."""

    async def test_includes_memory_topics(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "Your memory topics:" in ctx
        assert "personal" in ctx
        assert "preferences" in ctx

    async def test_no_memory_topics_in_shared_context(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces, shared_only=True)
        assert "Your memory topics:" not in ctx

    async def test_no_memory_topics_for_unknown_person(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "nobody", dev_workspaces)
        assert "Your memory topics:" not in ctx


class TestRoutines:
    """Tests for scheduled routines injection."""

    async def test_includes_routines(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "Household routines:" in ctx
        assert "morning_briefing" in ctx
        assert "weekly_grocery_check" in ctx

    async def test_routines_in_shared_context(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces, shared_only=True)
        assert "Household routines:" in ctx

    async def test_no_routines_without_file(self, tmp_path: Path) -> None:
        ctx = await build_context("hello", "alice", tmp_path)
        assert "Household routines:" not in ctx


class TestEdgeCases:
    """Edge cases and general behaviour."""

    async def test_missing_person_workspace(self, dev_workspaces: Path) -> None:
        # "nobody" has no workspace directory — should not raise
        ctx = await build_context("hello", "nobody", dev_workspaces)
        assert isinstance(ctx, str)
        assert "Current time:" in ctx

    async def test_includes_current_time(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "Current time:" in ctx

    async def test_includes_speaker_name(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "You are talking to: alice" in ctx
