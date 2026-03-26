"""APScheduler wrapper — registers routines from ROUTINES.md and plugin definitions."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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
_RESULTS_FILE = "household/.routine_results.json"


class Scheduler:
    """Manages scheduled routines backed by APScheduler."""

    def __init__(
        self,
        loop: AgentLoop,
        workspaces: Path,
        timezone: str | None = None,
        dispatcher: Any = None,
    ) -> None:
        self._loop = loop
        self._workspaces = workspaces
        self._dispatcher = dispatcher
        self._tz = ZoneInfo(timezone) if timezone else None
        scheduler_kwargs: dict[str, Any] = {}
        if self._tz is not None:
            scheduler_kwargs["timezone"] = self._tz
        self._scheduler = AsyncIOScheduler(**scheduler_kwargs)
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

    def _save_last_run(self, job_id: str, result: str = "") -> None:
        """Record that a routine just ran, and store its result."""
        path = self._workspaces / _LAST_RUN_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self._load_last_runs()
        data[job_id] = datetime.now(UTC).isoformat()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Save result text (truncate to keep file reasonable)
        results_path = self._workspaces / _RESULTS_FILE
        try:
            results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
        except (json.JSONDecodeError, OSError):
            results = {}
        results[job_id] = result[:8000] if result else ""
        results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    def _list_members(self) -> list[str]:
        """Enumerate household member workspace directories."""
        skip = {"household", "plugins"}
        if not self._workspaces.is_dir():
            return []
        return sorted(
            d.name
            for d in self._workspaces.iterdir()
            if d.is_dir()
            and d.name not in skip
            and not d.name.startswith(".")
            and not d.name.startswith("group-")
        )

    def _make_routine_func(
        self, job_id: str, description: str, target: str | None = None,
    ) -> Any:
        """Create the async callable for a routine job.

        The routine executes the LLM agent, then the *scheduler* delivers the
        result via the channel dispatcher.  The LLM no longer needs to call
        ``message_send`` itself — it just produces the output text.

        *target* controls delivery:
        - ``None`` → group chat (household)
        - ``"each_member"`` → run once per member, DM each
        - a person name → run with that person's context, DM them
        """
        loop = self._loop
        scheduler = self

        async def _run_for_person(person: str) -> str:
            """Run the routine for a single person and deliver via DM."""
            result = await loop.run(
                f"[Scheduled routine] {description}",
                person,
                call_type=CallType.ROUTINE,
            )
            if result and result.strip() and scheduler._dispatcher:
                await scheduler._dispatcher.send(
                    person, f"📋 *{description}*\n\n{result}",
                )
            return result

        async def _run_routine() -> str:
            logger.info("Routine fired: %s (target=%s)", description, target or "group")
            try:
                if target == "each_member":
                    members = scheduler._list_members()
                    results: list[str] = []
                    for member in members:
                        try:
                            r = await _run_for_person(member)
                            results.append(r)
                        except Exception:
                            logger.exception(
                                "Routine failed for member %s: %s", member, description,
                            )
                    combined = "\n---\n".join(r for r in results if r.strip())
                    scheduler._save_last_run(job_id, combined)
                    logger.info(
                        "Routine completed for %d members: %s", len(members), description,
                    )
                    return combined

                if target:
                    # Specific person
                    result = await _run_for_person(target)
                    scheduler._save_last_run(job_id, result)
                    logger.info("Routine completed: %s (response length: %d)", description, len(result))
                    return result

                # Default: household group chat
                result = await loop.run(
                    f"[Scheduled routine] {description}",
                    HOUSEHOLD_WORKSPACE,
                    call_type=CallType.ROUTINE,
                )
                scheduler._save_last_run(job_id, result)
                logger.info("Routine completed: %s (response length: %d)", description, len(result))

                if result and result.strip() and scheduler._dispatcher:
                    try:
                        await scheduler._dispatcher.send_group(
                            "", f"📋 *{description}*\n\n{result}",
                        )
                    except Exception:
                        logger.exception("Failed to deliver routine result: %s", description)

                return result
            except Exception:
                logger.exception("Routine failed: %s", description)
                return ""

        return _run_routine

    def _add_routine_job(
        self,
        job_id: str,
        description: str,
        trigger_type: str,
        trigger_kwargs: dict[str, Any],
        target: str | None = None,
    ) -> None:
        trigger = self._make_trigger(trigger_type, trigger_kwargs)

        self._scheduler.add_job(
            self._make_routine_func(job_id, description, target=target),
            trigger=trigger,
            id=job_id,
            name=description,
            replace_existing=True,
            misfire_grace_time=900,  # 15 min grace period to avoid silent skips
        )
        self._job_count += 1
        logger.info("Registered routine: %s (%s, target=%s)", job_id, trigger, target or "group")

    def load_routines_md(self) -> int:
        """Parse ROUTINES.md and register all routines. Returns count added."""
        routines = parse_routines_md(self._workspaces)
        for r in routines:
            self._add_routine_job(
                job_id=f"routine:{r.name}",
                description=r.description,
                trigger_type=r.trigger_type,
                trigger_kwargs=r.trigger_kwargs,
                target=r.target,
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
                display_time = (
                    next_fire.astimezone(self._tz) if self._tz else next_fire
                )
                logger.info(
                    "Missed routine detected: %s (should have fired %s)",
                    job.name,
                    display_time,
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

    async def run_now(self, name: str) -> str | None:
        """Trigger a routine by slug name immediately. Returns result text or None if not found."""
        job_id = f"routine:{name}"
        job = self._scheduler.get_job(job_id)
        if job is None:
            return None
        logger.info("Manual trigger: %s", job.name)
        # Run the routine function directly (same as scheduled execution)
        result = await job.func()
        return result

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
