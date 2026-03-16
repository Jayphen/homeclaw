"""Unit tests for the context builder against dev fixtures."""

from pathlib import Path

import pytest

from homeclaw.agent.context import build_context


class TestAliceContext:
    """Tests for Alice's context output."""

    async def test_includes_memory_facts(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "Vegetarian" in ctx
        assert "Has a cat named Mochi" in ctx

    async def test_includes_preferences(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "alice", dev_workspaces)
        assert "reminder_time: 7:30am" in ctx

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

    async def test_includes_bob_facts(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "bob", dev_workspaces)
        assert "Runs on weekends" in ctx
        assert "cooking" in ctx.lower()
        assert "renovation" in ctx.lower()

    async def test_does_not_include_alice_facts(self, dev_workspaces: Path) -> None:
        ctx = await build_context("hello", "bob", dev_workspaces)
        assert "Vegetarian" not in ctx
        assert "Mochi" not in ctx


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
