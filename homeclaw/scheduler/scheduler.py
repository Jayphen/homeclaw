"""APScheduler wrapper — registers routines from ROUTINES.md and plugin definitions."""

from __future__ import annotations

import logging
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

    def _add_routine_job(
        self,
        job_id: str,
        description: str,
        trigger_type: str,
        trigger_kwargs: dict[str, Any],
    ) -> None:
        trigger = self._make_trigger(trigger_type, trigger_kwargs)

        async def _run_routine() -> None:
            logger.info("Routine fired: %s", description)
            try:
                await self._loop.run(
                    f"[Scheduled routine] {description}",
                    HOUSEHOLD_WORKSPACE,
                    call_type=CallType.ROUTINE,
                )
            except Exception:
                logger.exception("Routine failed: %s", description)

        self._scheduler.add_job(
            _run_routine,
            trigger=trigger,
            id=job_id,
            name=description,
            replace_existing=True,
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
