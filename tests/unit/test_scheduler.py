"""Tests for scheduler routine execution."""

from __future__ import annotations

from typing import Any

import pytest

from homeclaw import HOUSEHOLD_WORKSPACE
from homeclaw.agent.routing import CallType
from homeclaw.scheduler.scheduler import Scheduler


class _FakeLoop:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run(
        self,
        user_message: str,
        person: str,
        **kwargs: Any,
    ) -> str:
        self.calls.append(
            {
                "user_message": user_message,
                "person": person,
                **kwargs,
            }
        )
        return "routine output"


@pytest.mark.asyncio
async def test_household_routine_runs_without_persisted_history(tmp_path: Any) -> None:
    loop = _FakeLoop()
    scheduler = Scheduler(loop, tmp_path)  # type: ignore[arg-type]

    routine = scheduler._make_routine_func("routine:brief", "Morning brief")
    result = await routine()

    assert result == "routine output"
    assert loop.calls == [
        {
            "user_message": "[Scheduled routine] Morning brief",
            "person": HOUSEHOLD_WORKSPACE,
            "call_type": CallType.ROUTINE,
            "persist_history": False,
        }
    ]


@pytest.mark.asyncio
async def test_person_routine_runs_without_persisted_history(tmp_path: Any) -> None:
    loop = _FakeLoop()
    scheduler = Scheduler(loop, tmp_path)  # type: ignore[arg-type]

    routine = scheduler._make_routine_func("routine:brief", "Morning brief", target="alice")
    result = await routine()

    assert result == "routine output"
    assert loop.calls[0]["person"] == "alice"
    assert loop.calls[0]["call_type"] == CallType.ROUTINE
    assert loop.calls[0]["persist_history"] is False
