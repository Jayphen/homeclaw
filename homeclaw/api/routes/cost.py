"""Cost summary API route."""

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Query

from homeclaw.agent.cost_tracker import CostTracker
from homeclaw.api.deps import AuthDep, get_config

router = APIRouter(prefix="/api/cost", tags=["cost"])


def _round_breakdown(
    data: dict[str, dict[str, float | int]],
) -> dict[str, dict[str, Any]]:
    return {
        k: {
            mk: round(mv, 6) if isinstance(mv, float) else mv
            for mk, mv in v.items()
        }
        for k, v in data.items()
    }


@router.get("/summary", dependencies=[AuthDep])
async def cost_summary(
    days: int = Query(default=7, ge=1, le=365),
) -> dict[str, Any]:
    workspaces = get_config().workspaces.resolve()
    tracker = CostTracker(workspaces)
    entries = tracker.read_entries(days=days)

    total_cost = 0.0
    total_input = 0
    total_cached = 0
    by_model: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"calls": 0, "cost_usd": 0.0}
    )
    by_call_type: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"calls": 0, "cost_usd": 0.0}
    )

    for e in entries:
        total_cost += e.estimated_cost_usd
        total_input += e.input_tokens
        total_cached += e.cached_tokens

        by_model[e.model]["calls"] += 1  # type: ignore[operator]
        by_model[e.model]["cost_usd"] += e.estimated_cost_usd

        by_call_type[e.call_type]["calls"] += 1  # type: ignore[operator]
        by_call_type[e.call_type]["cost_usd"] += e.estimated_cost_usd

    projected_monthly = (
        (total_cost / days * 30) if days > 0 and entries else 0.0
    )
    cache_hit_rate = (total_cached / total_input) if total_input > 0 else 0.0

    return {
        "period_days": days,
        "total_calls": len(entries),
        "total_cost_usd": round(total_cost, 6),
        "projected_monthly_usd": round(projected_monthly, 4),
        "by_model": _round_breakdown(by_model),
        "by_call_type": _round_breakdown(by_call_type),
        "cache_hit_rate": round(cache_hit_rate, 4),
    }
