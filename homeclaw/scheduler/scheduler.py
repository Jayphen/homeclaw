"""APScheduler wrapper — registers routines from ROUTINES.md and plugin definitions."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from homeclaw import HOUSEHOLD_WORKSPACE
from homeclaw.agent.loop import AgentLoop
from homeclaw.agent.routing import CallType
from homeclaw.plugins.interface import RoutineDefinition
from homeclaw.scheduler.routines import parse_routines_md

logger = logging.getLogger(__name__)

_LAST_RUN_FILE = "household/.routine_last_run.json"


class Scheduler:
    """Manages scheduled routines backed by APScheduler."""

    def __init__(self, loop: AgentLoop, workspaces: Path) -> None:
        self._loop = loop
        self._workspaces = workspaces
        self._scheduler = AsyncIOScheduler()
        self._job_count = 0

    def _make_trigger(
        self, trigger_type: str, trigger_kwargs: dict[str, Any]
    ) -> CronTrigger | IntervalTrigger:
        if trigger_type == "cron":
            return CronTrigger(**trigger_kwargs)
        return IntervalTrigger(**trigger_kwargs)

    def _load_last_runs(self) -> dict[str, str]:
        """Load last-run timestamps from disk."""
        path = self._workspaces / _LAST_RUN_FILE
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_last_run(self, job_id: str) -> None:
        """Record that a routine just ran."""
        path = self._workspaces / _LAST_RUN_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self._load_last_runs()
        data[job_id] = datetime.now(UTC).isoformat()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _make_routine_func(self, job_id: str, description: str) -> Any:
        """Create the async callable for a routine job."""
        loop = self._loop
        scheduler = self

        async def _run_routine() -> None:
            logger.info("Routine fired: %s", description)
            try:
                await loop.run(
                    f"[Scheduled routine] {description}",
                    HOUSEHOLD_WORKSPACE,
                    call_type=CallType.ROUTINE,
                )
                scheduler._save_last_run(job_id)
            except Exception:
                logger.exception("Routine failed: %s", description)

        return _run_routine

    def _add_routine_job(
        self,
        job_id: str,
        description: str,
        trigger_type: str,
        trigger_kwargs: dict[str, Any],
    ) -> None:
        trigger = self._make_trigger(trigger_type, trigger_kwargs)

        self._scheduler.add_job(
            self._make_routine_func(job_id, description),
            trigger=trigger,
            id=job_id,
            name=description,
            replace_existing=True,
            misfire_grace_time=900,  # 15 min grace period to avoid silent skips
        )
        self._job_count += 1
        logger.info("Registered routine: %s (%s)", job_id, trigger)

    def load_routines_md(self) -> int:
        """Parse ROUTINES.md and register all routines. Returns count added."""
        routines = parse_routines_md(self._workspaces)
        for r in routines:
            self._add_routine_job(
                job_id=f"routine:{r.name}",
                description=r.description,
                trigger_type=r.trigger_type,
                trigger_kwargs=r.trigger_kwargs,
            )
        return len(routines)

    def load_plugin_routines(self, plugin_name: str, routines: list[RoutineDefinition]) -> int:
        """Register routines from a plugin. Returns count added."""
        count = 0
        for r in routines:
            # Plugin cron strings are standard 5-field cron expressions
            parts = r.cron.split()
            if len(parts) != 5:
                logger.warning("Invalid cron expression from plugin %s: %r", plugin_name, r.cron)
                continue
            trigger_kwargs: dict[str, Any] = {
                "minute": parts[0],
                "hour": parts[1],
                "day": parts[2],
                "month": parts[3],
                "day_of_week": parts[4],
            }
            job_id = f"plugin:{plugin_name}:{r.description[:40]}"
            self._add_routine_job(
                job_id=job_id,
                description=f"[{plugin_name}] {r.description}",
                trigger_type="cron",
                trigger_kwargs=trigger_kwargs,
            )
            count += 1
        return count

    def start(self) -> None:
        """Start the scheduler. Must be called after routines are loaded."""
        if self._job_count == 0:
            logger.info("No routines registered — scheduler not started")
            return
        self._scheduler.start()
        logger.info("Scheduler started with %d routines", self._job_count)

    async def fire_missed(self) -> int:
        """Check for routines that should have run while the server was down.

        Compares each routine's trigger against its last recorded run time.
        If the trigger would have fired between last_run and now, queues the
        routine to run immediately.  Returns count of missed routines fired.
        """
        last_runs = self._load_last_runs()
        if not last_runs:
            # First run ever — nothing to compare against, record current time
            # for all jobs so the *next* restart can detect misses.
            for job in self._scheduler.get_jobs():
                self._save_last_run(job.id)
            return 0

        now = datetime.now(UTC)
        fired = 0
        for job in self._scheduler.get_jobs():
            last_iso = last_runs.get(job.id)
            if not last_iso:
                # New routine added while server was up — no missed run
                self._save_last_run(job.id)
                continue
            last_dt = datetime.fromisoformat(last_iso)
            # Ask the trigger: when would you have fired after last_run?
            next_fire = job.trigger.get_next_fire_time(None, last_dt)
            if next_fire is not None and next_fire < now:
                logger.info(
                    "Missed routine detected: %s (should have fired %s)",
                    job.name,
                    next_fire,
                )
                # Fire in background so we don't block startup
                asyncio.ensure_future(job.func())
                fired += 1
        if fired:
            logger.info("Fired %d missed routine(s) on startup", fired)
        return fired

    def shutdown(self) -> None:
        """Shutdown the scheduler gracefully."""
        if self._scheduler.running:
            try:
                self._scheduler.shutdown(wait=False)
            except RuntimeError:
                pass  # Event loop already closed
            logger.info("Scheduler shut down")

    def reload_routines(self) -> int:
        """Re-parse ROUTINES.md and replace all routine jobs. Returns new count."""
        # Remove existing routine jobs (keep plugin jobs)
        for job in self._scheduler.get_jobs():
            if job.id.startswith("routine:"):
                job.remove()
        old_count = self._job_count
        self._job_count = 0
        count = self.load_routines_md()
        logger.info("Reloaded routines: %d (was %d)", count, old_count)
        # Start the scheduler if it wasn't running and we now have jobs
        if count > 0 and not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler started after reload with %d routines", count)
        return count

    async def run_now(self, name: str) -> bool:
        """Trigger a routine by slug name immediately. Returns True if found."""
        job_id = f"routine:{name}"
        job = self._scheduler.get_job(job_id)
        if job is None:
            return False
        logger.info("Manual trigger: %s", job.name)
        # Run the routine function directly (same as scheduled execution)
        await job.func()
        return True

    @property
    def job_count(self) -> int:
        return self._job_count

    @property
    def jobs(self) -> list[dict[str, Any]]:
        """Return a summary of all registered jobs."""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in self._scheduler.get_jobs()
        ]
