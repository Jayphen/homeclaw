"""Tests for the ROUTINES.md parser."""

from pathlib import Path

import pytest

from homeclaw.scheduler.routines import ParsedRoutine, parse_routines_md, _parse_schedule, _parse_time, _ordinal_day_range, add_routine, update_routine


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

    # --- New patterns ---

    def test_cron_expression_weekday_morning(self):
        assert _parse_schedule("30 7 * * 1-5") == (
            "cron", {"minute": "30", "hour": "7", "day": "*", "month": "*", "day_of_week": "1-5"}
        )

    def test_cron_expression_monthly(self):
        assert _parse_schedule("0 9 1 * *") == (
            "cron", {"minute": "0", "hour": "9", "day": "1", "month": "*", "day_of_week": "*"}
        )

    def test_every_other_day(self):
        result = _parse_schedule("Every other day at 7:30am")
        assert result == ("interval", {"days": 2, "hours": 7, "minutes": 30})

    def test_every_other_tuesday(self):
        result = _parse_schedule("Every other Tuesday at 9:00am")
        assert result[0] == "interval"
        assert result[1]["weeks"] == 2

    def test_every_n_weeks_on_day(self):
        result = _parse_schedule("Every 3 weeks on Wednesday at 10:00am")
        assert result[0] == "interval"
        assert result[1]["weeks"] == 3

    def test_every_n_weeks_simple(self):
        assert _parse_schedule("Every 2 weeks") == ("interval", {"weeks": 2})

    def test_monthly_on_the_15th(self):
        assert _parse_schedule("Monthly on the 15th at 9:00am") == (
            "cron", {"day": 15, "hour": 9, "minute": 0}
        )

    def test_monthly_on_the_1st(self):
        assert _parse_schedule("Monthly on the 1st at 10:00am") == (
            "cron", {"day": 1, "hour": 10, "minute": 0}
        )

    def test_first_monday_of_month(self):
        result = _parse_schedule("1st Monday of the month at 10:00am")
        assert result == ("cron", {"day_of_week": "mon", "day": "1-7", "hour": 10, "minute": 0})

    def test_last_friday_of_month(self):
        result = _parse_schedule("Last Friday of the month at 3:00pm")
        assert result == ("cron", {"day_of_week": "fri", "day": "25-31", "hour": 15, "minute": 0})

    def test_second_wednesday_of_month(self):
        result = _parse_schedule("2nd Wednesday of the month at 9:00am")
        assert result == ("cron", {"day_of_week": "wed", "day": "8-14", "hour": 9, "minute": 0})

    def test_fourth_thursday_of_month(self):
        result = _parse_schedule("Fourth Thursday of month at 6:00pm")
        assert result == ("cron", {"day_of_week": "thu", "day": "22-28", "hour": 18, "minute": 0})

    def test_invalid_still_raises(self):
        with pytest.raises(ValueError, match="Cannot parse schedule"):
            _parse_schedule("whenever I feel like it")

    def test_error_message_mentions_cron(self):
        with pytest.raises(ValueError, match="cron"):
            _parse_schedule("on a whim")


class TestOrdinalDayRange:
    def test_first(self):
        assert _ordinal_day_range("1st") == "1-7"
        assert _ordinal_day_range("first") == "1-7"

    def test_second(self):
        assert _ordinal_day_range("2nd") == "8-14"

    def test_last(self):
        assert _ordinal_day_range("last") == "25-31"

    def test_unknown_defaults(self):
        assert _ordinal_day_range("fifth") == "1-7"


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


class TestUpdateRoutine:
    def test_update_action(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text(
            "# Routines\n\n"
            "## Morning briefing\n"
            "- **Schedule**: Every weekday at 7:30am\n"
            "- **Action**: Send each household member their daily summary\n"
        )
        assert update_routine(tmp_path, "morning_briefing", action="Send daily summary with top news headlines and weather")
        routines = parse_routines_md(tmp_path)
        assert len(routines) == 1
        assert "top news headlines" in routines[0].description

    def test_update_schedule(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text(
            "# Routines\n\n"
            "## Morning briefing\n"
            "- **Schedule**: Every weekday at 7:30am\n"
            "- **Action**: Send daily summary\n"
        )
        assert update_routine(tmp_path, "morning_briefing", schedule="Every day at 8:00am")
        routines = parse_routines_md(tmp_path)
        assert routines[0].trigger_kwargs == {"hour": 8, "minute": 0}

    def test_update_not_found(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text("# Routines\n")
        assert not update_routine(tmp_path, "nonexistent", action="something")

    def test_update_preserves_other_routines(self, dev_workspaces: Path):
        original = parse_routines_md(dev_workspaces)
        update_routine(dev_workspaces, "morning_briefing", action="Updated action")
        updated = parse_routines_md(dev_workspaces)
        assert len(updated) == len(original)
        # Other routines unchanged
        by_name = {r.name: r for r in updated}
        assert "grocery list" in by_name["weekly_grocery_check"].description

    def test_update_invalid_schedule_raises(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text(
            "# Routines\n\n"
            "## Test\n"
            "- **Schedule**: Every day at 8:00am\n"
            "- **Action**: Do stuff\n"
        )
        with pytest.raises(ValueError, match="Cannot parse schedule"):
            update_routine(tmp_path, "test", schedule="whenever")


class TestRoutineTarget:
    """Tests for the Target field on routines."""

    def test_parse_target_field(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text(
            "# Routines\n\n"
            "## Morning briefing\n"
            "- **Schedule**: Every weekday at 7:30am\n"
            "- **Target**: stephen\n"
            "- **Action**: Send daily summary\n"
        )
        routines = parse_routines_md(tmp_path)
        assert len(routines) == 1
        assert routines[0].target == "stephen"

    def test_parse_each_member_target(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text(
            "# Routines\n\n"
            "## Digest\n"
            "- **Schedule**: Every day at 8:00am\n"
            "- **Target**: each_member\n"
            "- **Action**: Personalised digest\n"
        )
        routines = parse_routines_md(tmp_path)
        assert routines[0].target == "each_member"

    def test_household_target_normalised_to_none(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text(
            "# Routines\n\n"
            "## Alert\n"
            "- **Schedule**: Every day at 9:00am\n"
            "- **Target**: household\n"
            "- **Action**: Group alert\n"
        )
        routines = parse_routines_md(tmp_path)
        assert routines[0].target is None

    def test_no_target_defaults_to_none(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        (tmp_path / "household" / "ROUTINES.md").write_text(
            "# Routines\n\n"
            "## Reminder\n"
            "- **Schedule**: Every day at 10:00am\n"
            "- **Action**: Something\n"
        )
        routines = parse_routines_md(tmp_path)
        assert routines[0].target is None

    def test_add_routine_with_target(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        add_routine(tmp_path, "Test", "Every day at 8:00am", "Do stuff", target="stephen")
        routines = parse_routines_md(tmp_path)
        assert routines[0].target == "stephen"

    def test_add_routine_without_target(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        add_routine(tmp_path, "Test", "Every day at 8:00am", "Do stuff")
        routines = parse_routines_md(tmp_path)
        assert routines[0].target is None

    def test_update_routine_target(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        add_routine(tmp_path, "Test", "Every day at 8:00am", "Do stuff", target="stephen")
        update_routine(tmp_path, "test", target="each_member")
        routines = parse_routines_md(tmp_path)
        assert routines[0].target == "each_member"

    def test_update_routine_clear_target(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        add_routine(tmp_path, "Test", "Every day at 8:00am", "Do stuff", target="stephen")
        update_routine(tmp_path, "test", target=None)
        routines = parse_routines_md(tmp_path)
        assert routines[0].target is None

    def test_update_routine_preserves_target(self, tmp_path: Path):
        (tmp_path / "household").mkdir()
        add_routine(tmp_path, "Test", "Every day at 8:00am", "Do stuff", target="stephen")
        update_routine(tmp_path, "test", action="New action")
        routines = parse_routines_md(tmp_path)
        assert routines[0].target == "stephen"
        assert "New action" in routines[0].description

    def test_dev_fixtures_have_no_target(self, dev_workspaces: Path):
        """Existing routines without Target field default to None."""
        routines = parse_routines_md(dev_workspaces)
        for r in routines:
            assert r.target is None
