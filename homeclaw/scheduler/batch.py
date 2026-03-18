"""Batch scheduler — submits routine LLM calls via Anthropic Message Batches API.

The Batches API gives a 50% discount on all tokens. Routines don't need
real-time responses, so batching is a natural fit. Falls back to real-time
calls if batch results take too long.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, get_args

import anthropic

logger = logging.getLogger(__name__)

_BATCH_TIMEOUT = timedelta(minutes=30)

BatchResultStatus = Literal["succeeded", "failed"]
BatchProcessingStatus = Literal["ended", "errored", "canceled", "expired"]

# Batch processing_status values that mean "no more results coming".
_TERMINAL_STATUSES: frozenset[str] = frozenset(get_args(BatchProcessingStatus))


@dataclass
class RoutineRun:
    """A single routine invocation waiting to be batched."""

    custom_id: str
    description: str
    system: str
    messages: list[dict[str, Any]]
    model: str
    max_tokens: int = 512


@dataclass
class PendingBatch:
    """A submitted batch waiting for results."""

    batch_id: str
    submitted_at: datetime
    routine_runs: list[RoutineRun]


class BatchScheduler:
    """Accumulates routine LLM calls and submits them as Anthropic batches.

    Usage:
        1. Call add_routine() to queue routine runs
        2. Call submit() to send the batch to Anthropic
        3. Call poll_and_dispatch() periodically to check for results
    """

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._queue: list[RoutineRun] = []
        self._pending: list[PendingBatch] = []
        self._results: list[dict[str, Any]] = []
        # Protects _queue and _pending from concurrent submit/poll races.
        self._lock = asyncio.Lock()

    def add_routine(self, run: RoutineRun) -> None:
        """Queue a routine run for the next batch submission."""
        self._queue.append(run)
        logger.debug("Queued routine for batch: %s", run.custom_id)

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    async def submit(self) -> str | None:
        """Submit all queued routines as a single batch. Returns batch_id."""
        async with self._lock:
            return await self._submit_inner()

    async def _submit_inner(self) -> str | None:
        if not self._queue:
            return None

        requests = [
            {
                "custom_id": run.custom_id,
                "params": {
                    "model": run.model,
                    "max_tokens": run.max_tokens,
                    "system": run.system,
                    "messages": run.messages,
                },
            }
            for run in self._queue
        ]

        try:
            batch = await self._client.messages.batches.create(
                requests=requests,  # type: ignore[arg-type]
            )
        except Exception:
            logger.exception("Failed to submit batch with %d routines", len(self._queue))
            return None

        pending = PendingBatch(
            batch_id=batch.id,
            submitted_at=datetime.now(UTC),
            routine_runs=list(self._queue),
        )
        self._pending.append(pending)
        self._queue.clear()

        logger.info(
            "Submitted batch %s with %d routines",
            batch.id,
            len(pending.routine_runs),
        )
        return batch.id

    async def poll_and_dispatch(self) -> list[dict[str, Any]]:
        """Check pending batches for results. Returns completed results."""
        async with self._lock:
            return await self._poll_inner()

    async def _poll_inner(self) -> list[dict[str, Any]]:
        completed: list[dict[str, Any]] = []
        still_pending: list[PendingBatch] = []

        for pending in self._pending:
            try:
                batch = await self._client.messages.batches.retrieve(pending.batch_id)
            except Exception:
                logger.exception("Failed to retrieve batch %s", pending.batch_id)
                still_pending.append(pending)
                continue

            if batch.processing_status == "ended":
                results = await self._collect_results(pending, batch)
                completed.extend(results)
                logger.info(
                    "Batch %s completed: %d results",
                    pending.batch_id,
                    len(results),
                )
            elif batch.processing_status in _TERMINAL_STATUSES:
                logger.warning(
                    "Batch %s reached terminal status '%s' — discarding",
                    pending.batch_id,
                    batch.processing_status,
                )
            elif self._is_timed_out(pending):
                logger.warning(
                    "Batch %s timed out after %s — results discarded",
                    pending.batch_id,
                    _BATCH_TIMEOUT,
                )
            else:
                still_pending.append(pending)

        self._pending = still_pending
        self._results.extend(completed)
        return completed

    async def _collect_results(self, pending: PendingBatch, batch: Any) -> list[dict[str, Any | BatchResultStatus]]:
        """Collect results from a completed batch."""
        results: list[dict[str, Any]] = []
        runs_by_id = {r.custom_id: r for r in pending.routine_runs}

        results_iter = await self._client.messages.batches.results(pending.batch_id)
        async for entry in results_iter:
            run = runs_by_id.get(entry.custom_id)
            if run is None:
                continue

            if entry.result.type == "succeeded":
                msg = entry.result.message
                content = "\n".join(b.text for b in msg.content if b.type == "text")
                status: BatchResultStatus = "succeeded"
            else:
                content = ""
                status = "failed"
            results.append(
                {
                    "custom_id": entry.custom_id,
                    "description": run.description,
                    "content": content,
                    "status": status,
                }
            )

        return results

    def _is_timed_out(self, pending: PendingBatch) -> bool:
        return datetime.now(UTC) - pending.submitted_at > _BATCH_TIMEOUT
