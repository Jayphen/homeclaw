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
        """No person's facts should appear in any context (Layer 1 removed)."""
        ctx = await build_context("hello", "bob", dev_workspaces)
        assert "Vegetarian" not in ctx
        assert "Mochi" not in ctx
        assert "Runs on weekends" not in ctx


class TestEdgeCases:
    """Edge cases and general behaviour."""

    async def test_missing_memory_json(self, dev_workspaces: Path) -> None:
        # "nobody" has no directory or memory.json — should not raise
        ctx = await build_context("hello", "nobody", dev_workspaces)
        assert isinstance(ctx, str)
        assert "Current time:" in ctx

    async def test_includes_current_time(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "Current time:" in ctx
