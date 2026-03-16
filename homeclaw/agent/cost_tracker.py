"""Lightweight cost tracker — logs token usage per LLM call to a JSONL file."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_COST_LOG_FILE = "cost_log.jsonl"
_RETENTION_DAYS = 30


class CostEntry(BaseModel):
    ts: str
    call_type: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    estimated_cost_usd: float
    person: str


class ModelPricing(BaseModel):
    input_per_mtok: float
    output_per_mtok: float
    cached_input_per_mtok: float = 0.0


def load_prices(prices_path: Path | None = None) -> dict[str, ModelPricing]:
    """Load model pricing from prices.json."""
    if prices_path is None:
        prices_path = Path(__file__).parent.parent.parent / "prices.json"
    if not prices_path.exists():
        return {}
    data = json.loads(prices_path.read_text())
    return {k: ModelPricing(**v) for k, v in data.items()}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int,
    prices: dict[str, ModelPricing],
) -> float:
    """Estimate cost in USD for a single LLM call."""
    # Strip provider prefix (e.g. "anthropic/claude-sonnet-4-6" → "claude-sonnet-4-6")
    model_key = model.split("/")[-1] if "/" in model else model
    pricing = prices.get(model_key) or prices.get(model)
    if pricing is None:
        return 0.0
    uncached_input = max(0, input_tokens - cached_tokens)
    cost = (
        (uncached_input / 1_000_000) * pricing.input_per_mtok
        + (cached_tokens / 1_000_000) * pricing.cached_input_per_mtok
        + (output_tokens / 1_000_000) * pricing.output_per_mtok
    )
    return round(cost, 8)


class CostTracker:
    """Tracks LLM costs by appending entries to a JSONL log file."""

    def __init__(self, workspaces: Path, prices_path: Path | None = None) -> None:
        self._log_path = workspaces / _COST_LOG_FILE
        self._prices = load_prices(prices_path)
        self._prune_old_entries()

    def _prune_old_entries(self) -> None:
        """Remove entries older than retention period on startup."""
        if not self._log_path.exists():
            return
        cutoff = (datetime.now(UTC) - timedelta(days=_RETENTION_DAYS)).isoformat()
        lines = self._log_path.read_text().strip().splitlines()
        kept = [
            line
            for line in lines
            if line and json.loads(line).get("ts", "") >= cutoff
        ]
        self._log_path.write_text("\n".join(kept) + "\n" if kept else "")

    def log(
        self,
        call_type: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        person: str,
        cached_tokens: int = 0,
    ) -> CostEntry:
        """Log a single LLM call and return the entry."""
        cost = estimate_cost(
            model, input_tokens, output_tokens, cached_tokens, self._prices
        )
        entry = CostEntry(
            ts=datetime.now(UTC).isoformat(),
            call_type=call_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            estimated_cost_usd=cost,
            person=person,
        )
        with self._log_path.open("a") as f:
            f.write(entry.model_dump_json() + "\n")
        logger.debug(
            "Cost: %s %s %d in/%d out → $%.6f",
            call_type, model, input_tokens, output_tokens, cost,
        )
        return entry

    def read_entries(self, days: int = 7) -> list[CostEntry]:
        """Read log entries from the last N days."""
        if not self._log_path.exists():
            return []
        cutoff = (
            datetime.now(UTC) - timedelta(days=days)
        ).isoformat()
        entries: list[CostEntry] = []
        for line in self._log_path.read_text().strip().splitlines():
            if not line:
                continue
            data = json.loads(line)
            if data.get("ts", "") >= cutoff:
                entries.append(CostEntry(**data))
        return entries
