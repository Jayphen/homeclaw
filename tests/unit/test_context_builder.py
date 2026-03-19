"""Unit tests for the context builder against dev fixtures."""

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
