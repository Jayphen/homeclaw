"""Tests for the ROUTINES.md parser."""

from pathlib import Path

import pytest

from homeclaw.scheduler.routines import ParsedRoutine, parse_routines_md, _parse_schedule, _parse_time


class TestParseTime:
    def test_am(self):
        assert _parse_time("7:30am") == (7, 30)

    def test_pm(self):
        assert _parse_time("6:00pm") == (18, 0)

    def test_pm_uppercase(self):
        assert _parse_time("6:00 PM") == (18, 0)

    def test_12am(self):
        assert _parse_time("12:00am") == (0, 0)

    def test_12pm(self):
        assert _parse_time("12:00pm") == (12, 0)

    def test_no_ampm(self):
        assert _parse_time("14:30") == (14, 30)

    def test_invalid(self):
        with pytest.raises(ValueError, match="Cannot parse time"):
            _parse_time("not a time")


class TestParseSchedule:
    def test_every_day_at(self):
        assert _parse_schedule("Every day at 7:30am") == (
            "cron", {"hour": 7, "minute": 30}
        )

    def test_every_weekday_at(self):
        assert _parse_schedule("Every weekday at 9:00am") == (
            "cron", {"day_of_week": "mon-fri", "hour": 9, "minute": 0}
        )

    def test_every_sunday_at(self):
        assert _parse_schedule("Every Sunday at 10:00am") == (
            "cron", {"day_of_week": "sun", "hour": 10, "minute": 0}
        )

    def test_every_monday_at(self):
        assert _parse_schedule("Every Monday at 9:00am") == (
            "cron", {"day_of_week": "mon", "hour": 9, "minute": 0}
        )

    def test_every_n_days(self):
        assert _parse_schedule("Every 3 days") == ("interval", {"days": 3})

    def test_every_n_hours(self):
        assert _parse_schedule("Every 2 hours") == ("interval", {"hours": 2})

    def test_every_n_minutes(self):
        assert _parse_schedule("Every 30 minutes") == ("interval", {"minutes": 30})

    def test_case_insensitive(self):
        assert _parse_schedule("every WEEKDAY at 8:00AM") == (
            "cron", {"day_of_week": "mon-fri", "hour": 8, "minute": 0}
        )

    def test_invalid_schedule(self):
        with pytest.raises(ValueError, match="Cannot parse schedule"):
            _parse_schedule("whenever I feel like it")


class TestParseRoutinesMd:
    def test_dev_fixtures(self, dev_workspaces: Path):
        """Parses the dev fixtures ROUTINES.md correctly."""
        routines = parse_routines_md(dev_workspaces)
        assert len(routines) == 4

        by_name = {r.name: r for r in routines}

        morning = by_name["morning_briefing"]
        assert morning.trigger_type == "cron"
        assert morning.trigger_kwargs == {"day_of_week": "mon-fri", "hour": 7, "minute": 30}

        grocery = by_name["weekly_grocery_check"]
        assert grocery.trigger_type == "cron"
        assert grocery.trigger_kwargs == {"day_of_week": "sun", "hour": 10, "minute": 0}

        plants = by_name["plant_watering_check"]
        assert plants.trigger_type == "interval"
        assert plants.trigger_kwargs == {"days": 3}

        contacts = by_name["contact_check_in"]
        assert contacts.trigger_type == "cron"
        assert contacts.trigger_kwargs == {"day_of_week": "mon", "hour": 9, "minute": 0}

    def test_descriptions_include_actions(self, dev_workspaces: Path):
        routines = parse_routines_md(dev_workspaces)
        by_name = {r.name: r for r in routines}

        assert "daily summary" in by_name["morning_briefing"].description
        assert "grocery list" in by_name["weekly_grocery_check"].description

    def test_missing_file_returns_empty(self, tmp_path: Path):
        assert parse_routines_md(tmp_path) == []

    def test_empty_file(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text("")
        assert parse_routines_md(tmp_path) == []

    def test_heading_style_schedule(self, tmp_path: Path):
        """Parses the planning-doc format where the heading IS the schedule."""
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text(
            "# Routines\n\n"
            "## Every day at 9:00 PM\n"
            "- Check if any plants are overdue for watering\n"
            "- Remind the relevant person if so\n"
        )
        routines = parse_routines_md(tmp_path)
        assert len(routines) == 1
        assert routines[0].trigger_type == "cron"
        assert routines[0].trigger_kwargs == {"hour": 21, "minute": 0}
        assert "plants" in routines[0].description.lower()

    def test_unparseable_schedule_skipped(self, tmp_path: Path):
        """Routines with unparseable schedules are silently skipped."""
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text(
            "# Routines\n\n"
            "## Some random heading\n"
            "- **Schedule**: whenever the moon is full\n"
            "- **Action**: howl\n\n"
            "## Valid routine\n"
            "- **Schedule**: Every day at 8:00am\n"
            "- **Action**: Do something useful\n"
        )
        routines = parse_routines_md(tmp_path)
        assert len(routines) == 1
        assert routines[0].name == "valid_routine"
