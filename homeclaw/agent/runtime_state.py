"""Runtime observability state for prompt, skill, and consolidation inspection."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, Field

from homeclaw.plugins.skills.verification import SkillVerificationReport

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class PromptSection(BaseModel):
    """A named section that contributed to the active system prompt."""

    name: str
    content: str


class PromptSnapshot(BaseModel):
    """Captured prompt composition for a specific session/run."""

    history_key: str
    person: str
    channel: str | None = None
    call_type: str
    model: str
    tool_count: int
    system_token_estimate: int
    sections: list[PromptSection]
    captured_at: datetime


class SkillActivationEvent(BaseModel):
    """Why and when a skill became active in the current process."""

    skill_name: str
    person: str
    reason: str
    tool_name: str | None = None
    activated_at: datetime


class ConsolidationEvent(BaseModel):
    """Outcome of a background consolidation attempt."""

    history_key: str
    person: str
    status: Literal["skipped", "succeeded", "failed"]
    reason: str
    unconsolidated_messages: int = 0
    history_tokens: int = 0
    chunk_size: int = 0
    saved_entries: int = 0
    model: str | None = None
    recorded_at: datetime


class ToolPolicyEntry(BaseModel):
    """Deterministic classification for a registered tool."""

    tool_name: str
    access: Literal["read", "write", "action", "unknown"]
    scope: Literal["personal", "household", "skill", "general"]
    categories: list[str]
    dm_enforcement: str | None = None
    routine_behavior: str | None = None


class RuntimeSnapshot(BaseModel):
    """Admin-facing runtime state snapshot."""

    prompt_snapshots: list[PromptSnapshot]
    recent_skill_activations: list[SkillActivationEvent]
    recent_skill_verifications: list[SkillVerificationReport]
    recent_consolidations: list[ConsolidationEvent]
    tool_policies: list[ToolPolicyEntry] = Field(default_factory=list)


class RuntimeObservability(Protocol):
    """Interface for recording runtime inspection data."""

    def record_prompt_snapshot(self, snapshot: PromptSnapshot) -> None: ...

    def record_skill_activation(self, event: SkillActivationEvent) -> None: ...

    def record_skill_verification(self, report: SkillVerificationReport) -> None: ...

    def record_consolidation(self, event: ConsolidationEvent) -> None: ...

    def snapshot(self) -> RuntimeSnapshot: ...


class InMemoryRuntimeObservability:
    """Small in-memory store for recent runtime events."""

    def __init__(self, *, max_prompt_snapshots: int = 20, max_recent_events: int = 50) -> None:
        self._max_prompt_snapshots = max_prompt_snapshots
        self._prompt_snapshots: dict[str, PromptSnapshot] = {}
        self._skill_activations: deque[SkillActivationEvent] = deque(maxlen=max_recent_events)
        self._skill_verifications: deque[SkillVerificationReport] = deque(maxlen=max_recent_events)
        self._consolidations: deque[ConsolidationEvent] = deque(maxlen=max_recent_events)

    def record_prompt_snapshot(self, snapshot: PromptSnapshot) -> None:
        self._prompt_snapshots.pop(snapshot.history_key, None)
        self._prompt_snapshots[snapshot.history_key] = snapshot
        while len(self._prompt_snapshots) > self._max_prompt_snapshots:
            oldest_key = next(iter(self._prompt_snapshots))
            self._prompt_snapshots.pop(oldest_key, None)

    def record_skill_activation(self, event: SkillActivationEvent) -> None:
        self._skill_activations.appendleft(event)

    def record_skill_verification(self, report: SkillVerificationReport) -> None:
        self._skill_verifications.appendleft(report)

    def record_consolidation(self, event: ConsolidationEvent) -> None:
        self._consolidations.appendleft(event)

    def snapshot(self) -> RuntimeSnapshot:
        prompt_snapshots = sorted(
            self._prompt_snapshots.values(),
            key=lambda item: item.captured_at,
            reverse=True,
        )
        return RuntimeSnapshot(
            prompt_snapshots=prompt_snapshots,
            recent_skill_activations=self._copy(self._skill_activations),
            recent_skill_verifications=self._copy(self._skill_verifications),
            recent_consolidations=self._copy(self._consolidations),
        )

    @staticmethod
    def _copy(items: Iterable[_ModelT]) -> list[_ModelT]:
        return [item.model_copy(deep=True) for item in items]


def now_utc() -> datetime:
    """Single helper so callers don't repeat the UTC import."""
    return datetime.now(UTC)
