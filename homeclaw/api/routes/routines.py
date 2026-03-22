"""Routines API — list, add, update, delete, and trigger household routines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homeclaw.api.deps import AdminDep, AuthDep, get_config, get_scheduler
from homeclaw.scheduler.routines import (
    add_routine,
    parse_routines_md,
    remove_routine,
    update_routine,
)

router = APIRouter(prefix="/api/routines", tags=["routines"])


def _last_runs(workspaces: Path) -> dict[str, str]:
    path = workspaces / "household" / ".routine_last_run.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


@router.get("", dependencies=[AuthDep])
async def list_routines() -> dict[str, Any]:
    """List all household routines with schedule, last-run, and next-run info."""
    config = get_config()
    workspaces = config.workspaces.resolve()
    routines = parse_routines_md(workspaces)
    last_runs = _last_runs(workspaces)
    scheduler = get_scheduler()

    # Build a lookup of next-run times from the live scheduler
    next_runs: dict[str, str | None] = {}
    if scheduler is not None:
        for job in scheduler.jobs:
            next_runs[job["id"]] = job["next_run"]

    items: list[dict[str, Any]] = []
    for r in routines:
        job_id = f"routine:{r.name}"
        items.append({
            "name": r.name,
            "description": r.description,
            "trigger_type": r.trigger_type,
            "trigger_kwargs": r.trigger_kwargs,
            "last_run": last_runs.get(job_id),
            "next_run": next_runs.get(job_id),
        })

    return {"routines": items, "count": len(items)}


class RoutineAddBody(BaseModel):
    title: str
    schedule: str
    action: str


@router.post("", dependencies=[AdminDep])
async def add_routine_endpoint(body: RoutineAddBody) -> dict[str, Any]:
    """Add a new routine. Admin only."""
    config = get_config()
    workspaces = config.workspaces.resolve()
    try:
        add_routine(workspaces, body.title, body.schedule, body.action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    scheduler = get_scheduler()
    if scheduler is not None:
        scheduler.reload_routines()

    return {"status": "added", "title": body.title}


class RoutineUpdateBody(BaseModel):
    schedule: str | None = None
    action: str | None = None
    title: str | None = None


@router.patch("/{name}", dependencies=[AdminDep])
async def update_routine_endpoint(
    name: str, body: RoutineUpdateBody,
) -> dict[str, Any]:
    """Update an existing routine. Admin only."""
    config = get_config()
    workspaces = config.workspaces.resolve()
    try:
        updated = update_routine(
            workspaces, name,
            schedule=body.schedule, action=body.action, title=body.title,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not updated:
        raise HTTPException(status_code=404, detail=f"Routine '{name}' not found")

    scheduler = get_scheduler()
    if scheduler is not None:
        scheduler.reload_routines()

    return {"status": "updated", "name": name}


@router.delete("/{name}", dependencies=[AdminDep])
async def delete_routine_endpoint(name: str) -> dict[str, Any]:
    """Remove a routine. Admin only."""
    config = get_config()
    workspaces = config.workspaces.resolve()
    removed = remove_routine(workspaces, name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Routine '{name}' not found")

    scheduler = get_scheduler()
    if scheduler is not None:
        scheduler.reload_routines()

    return {"status": "removed", "name": name}


@router.post("/{name}/run", dependencies=[AdminDep])
async def run_routine_endpoint(name: str) -> dict[str, Any]:
    """Trigger a routine to run immediately. Admin only."""
    scheduler = get_scheduler()
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not available")

    result = await scheduler.run_now(name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Routine '{name}' not found")

    return {"status": "completed", "name": name, "result": result}
