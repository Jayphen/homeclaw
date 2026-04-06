"""Tests for runtime observability snapshots."""

from __future__ import annotations

from homeclaw.agent.runtime_state import (
    ConsolidationEvent,
    InMemoryRuntimeObservability,
    PromptSection,
    PromptSnapshot,
    SkillActivationEvent,
    now_utc,
)
from homeclaw.plugins.skills.verification import (
    SkillVerificationCheck,
    SkillVerificationReport,
)


def test_runtime_snapshot_tracks_latest_prompt_per_history_key() -> None:
    state = InMemoryRuntimeObservability()
    ts = now_utc()

    state.record_prompt_snapshot(
        PromptSnapshot(
            history_key="alice",
            person="alice",
            call_type="conversation",
            channel=None,
            model="gpt-test-1",
            tool_count=3,
            system_token_estimate=100,
            sections=[PromptSection(name="context", content="first")],
            captured_at=ts,
        )
    )
    state.record_prompt_snapshot(
        PromptSnapshot(
            history_key="alice",
            person="alice",
            call_type="conversation",
            channel=None,
            model="gpt-test-2",
            tool_count=4,
            system_token_estimate=120,
            sections=[PromptSection(name="context", content="second")],
            captured_at=now_utc(),
        )
    )

    snapshot = state.snapshot()
    assert len(snapshot.prompt_snapshots) == 1
    assert snapshot.prompt_snapshots[0].model == "gpt-test-2"
    assert snapshot.prompt_snapshots[0].sections[0].content == "second"


def test_runtime_snapshot_exposes_recent_skill_and_consolidation_events() -> None:
    state = InMemoryRuntimeObservability()

    state.record_skill_activation(
        SkillActivationEvent(
            skill_name="weather",
            person="alice",
            reason="read_skill",
            tool_name=None,
            activated_at=now_utc(),
        )
    )
    state.record_skill_verification(
        SkillVerificationReport(
            skill_name="weather",
            owner="household",
            scope="household",
            source="skill_create",
            status="verified",
            verified_at=now_utc(),
            skill_dir="/tmp/weather",
            expected_tools=["weather__data_read"],
            available_tools=["weather__data_read"],
            missing_tools=[],
            dependency_warnings=[],
            checks=[
                SkillVerificationCheck(
                    name="load_skill",
                    status="passed",
                    detail="ok",
                )
            ],
        )
    )
    state.record_consolidation(
        ConsolidationEvent(
            history_key="alice",
            person="alice",
            status="succeeded",
            reason="ok",
            unconsolidated_messages=8,
            history_tokens=400,
            chunk_size=6,
            saved_entries=3,
            model="gpt-test-2",
            recorded_at=now_utc(),
        )
    )

    snapshot = state.snapshot()
    assert snapshot.recent_skill_activations[0].skill_name == "weather"
    assert snapshot.recent_skill_verifications[0].status == "verified"
    assert snapshot.recent_consolidations[0].saved_entries == 3
