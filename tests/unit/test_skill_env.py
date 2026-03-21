"""Tests for skill .env loading and substitution in homeclaw/plugins/skills/loader.py."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from homeclaw.plugins.skills.loader import (
    SkillDefinition,
    SkillPlugin,
    _load_skill_env,
    _substitute_env,
)


# ---------------------------------------------------------------------------
# _load_skill_env
# ---------------------------------------------------------------------------


class TestLoadSkillEnv:
    """Tests for _load_skill_env."""

    def test_reads_key_value_pairs(self, tmp_path: Path) -> None:
        """Basic KEY=VALUE lines are parsed correctly."""
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=abc123\nDB_HOST=localhost\n")
        result = _load_skill_env(tmp_path)
        assert result == {"API_KEY": "abc123", "DB_HOST": "localhost"}

    def test_skips_comments_and_blank_lines(self, tmp_path: Path) -> None:
        """Lines starting with # and blank lines are skipped."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# This is a comment\n"
            "\n"
            "KEY1=value1\n"
            "  # Another comment\n"
            "\n"
            "KEY2=value2\n"
        )
        result = _load_skill_env(tmp_path)
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_strips_quotes(self, tmp_path: Path) -> None:
        """Double and single quoted values have quotes stripped."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            'DOUBLE="hello world"\n'
            "SINGLE='goodbye world'\n"
        )
        result = _load_skill_env(tmp_path)
        assert result["DOUBLE"] == "hello world"
        assert result["SINGLE"] == "goodbye world"

    def test_no_env_file_returns_empty(self, tmp_path: Path) -> None:
        """No .env file → empty dict."""
        result = _load_skill_env(tmp_path)
        assert result == {}

    def test_whitespace_around_key_and_value(self, tmp_path: Path) -> None:
        """Leading/trailing whitespace on keys and values is stripped."""
        env_file = tmp_path / ".env"
        env_file.write_text("  MY_KEY  =  some_value  \n")
        result = _load_skill_env(tmp_path)
        assert result == {"MY_KEY": "some_value"}

    def test_empty_value(self, tmp_path: Path) -> None:
        """KEY= with empty value is stored as empty string."""
        env_file = tmp_path / ".env"
        env_file.write_text("EMPTY_KEY=\n")
        result = _load_skill_env(tmp_path)
        # Empty key is still stored (empty string value)
        assert "EMPTY_KEY" in result

    def test_value_with_equals_sign(self, tmp_path: Path) -> None:
        """Values containing = are preserved (partition splits on first =)."""
        env_file = tmp_path / ".env"
        env_file.write_text("URL=https://example.com?a=1&b=2\n")
        result = _load_skill_env(tmp_path)
        assert result["URL"] == "https://example.com?a=1&b=2"

    def test_line_without_equals_ignored(self, tmp_path: Path) -> None:
        """Lines without = are skipped."""
        env_file = tmp_path / ".env"
        env_file.write_text("GOOD=value\nBADLINE\nALSO_GOOD=yes\n")
        result = _load_skill_env(tmp_path)
        assert result == {"GOOD": "value", "ALSO_GOOD": "yes"}


# ---------------------------------------------------------------------------
# _substitute_env
# ---------------------------------------------------------------------------


class TestSubstituteEnv:
    """Tests for _substitute_env."""

    def test_replaces_known_var(self) -> None:
        """${VAR} in text is replaced with value from env dict."""
        result = _substitute_env("Hello ${NAME}!", {"NAME": "World"})
        assert result == "Hello World!"

    def test_unknown_var_left_as_is(self) -> None:
        """${UNKNOWN} not in env or os.environ is left as literal."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("UNKNOWN_VAR_XYZ", None)
            result = _substitute_env("key=${UNKNOWN_VAR_XYZ}", {})
        assert result == "key=${UNKNOWN_VAR_XYZ}"

    def test_os_environ_fallback(self) -> None:
        """${VAR} not in skill env falls back to os.environ."""
        with patch.dict(os.environ, {"FROM_OS": "os_value"}):
            result = _substitute_env("val=${FROM_OS}", {})
        assert result == "val=os_value"

    def test_skill_env_takes_precedence_over_os(self) -> None:
        """Skill env takes precedence over os.environ for same key."""
        with patch.dict(os.environ, {"SHARED": "from_os"}):
            result = _substitute_env("val=${SHARED}", {"SHARED": "from_skill"})
        assert result == "val=from_skill"

    def test_multiple_substitutions(self) -> None:
        """Multiple ${VAR} placeholders in one string."""
        result = _substitute_env(
            "${HOST}:${PORT}/api",
            {"HOST": "localhost", "PORT": "8080"},
        )
        assert result == "localhost:8080/api"

    def test_no_placeholders(self) -> None:
        """Text without ${...} is returned unchanged."""
        result = _substitute_env("plain text", {"KEY": "val"})
        assert result == "plain text"

    def test_empty_string(self) -> None:
        """Empty string input returns empty string."""
        result = _substitute_env("", {"KEY": "val"})
        assert result == ""

    def test_adjacent_placeholders(self) -> None:
        """Adjacent ${A}${B} both get replaced."""
        result = _substitute_env("${A}${B}", {"A": "hello", "B": "world"})
        assert result == "helloworld"

    def test_dollar_var_without_braces(self) -> None:
        """$VAR (no braces) is also substituted."""
        result = _substitute_env("url=$HA_URL/api", {"HA_URL": "http://ha.local"})
        assert result == "url=http://ha.local/api"

    def test_dollar_var_in_header(self) -> None:
        """$TOKEN in a header value is substituted."""
        result = _substitute_env("Bearer $HA_TOKEN", {"HA_TOKEN": "abc123"})
        assert result == "Bearer abc123"

    def test_mixed_syntax(self) -> None:
        """$VAR and ${VAR} in the same string both work."""
        result = _substitute_env(
            "$HA_URL/api with ${HA_TOKEN}",
            {"HA_URL": "http://ha", "HA_TOKEN": "tok"},
        )
        assert result == "http://ha/api with tok"

    def test_dollar_lowercase_not_matched(self) -> None:
        """$lowercase is not matched (only UPPER_CASE vars)."""
        result = _substitute_env("$notavar", {})
        assert result == "$notavar"


# ---------------------------------------------------------------------------
# SkillPlugin.env property
# ---------------------------------------------------------------------------


class TestSkillPluginEnv:
    """Tests for SkillPlugin.env property reading .env fresh."""

    def test_env_property_reads_env_file(self, tmp_path: Path) -> None:
        """SkillPlugin.env reads the .env file from the skill directory."""
        skill_dir = tmp_path / "my_skill"
        skill_dir.mkdir()
        (skill_dir / ".env").write_text("SECRET=hunter2\n")

        defn = SkillDefinition(name="test", description="test skill")
        plugin = SkillPlugin(defn, skill_dir, scope="household")

        assert plugin.env == {"SECRET": "hunter2"}

    def test_env_picks_up_new_file(self, tmp_path: Path) -> None:
        """Creating .env after init is picked up by the env property."""
        skill_dir = tmp_path / "my_skill"
        skill_dir.mkdir()

        defn = SkillDefinition(name="test", description="test skill")
        plugin = SkillPlugin(defn, skill_dir, scope="household")

        # No .env file yet
        assert plugin.env == {}

        # Create .env after init
        (skill_dir / ".env").write_text("NEW_KEY=new_value\n")

        # Should pick it up fresh
        assert plugin.env == {"NEW_KEY": "new_value"}

    def test_env_picks_up_edits(self, tmp_path: Path) -> None:
        """Modifying .env after init is reflected in subsequent reads."""
        skill_dir = tmp_path / "my_skill"
        skill_dir.mkdir()
        (skill_dir / ".env").write_text("KEY=old\n")

        defn = SkillDefinition(name="test", description="test skill")
        plugin = SkillPlugin(defn, skill_dir, scope="household")

        assert plugin.env == {"KEY": "old"}

        # Edit the .env file
        (skill_dir / ".env").write_text("KEY=new\nEXTRA=bonus\n")

        assert plugin.env == {"KEY": "new", "EXTRA": "bonus"}
