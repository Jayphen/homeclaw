"""Tests for homeclaw/plugins/skills/deps.py — skill dependency checker."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from homeclaw.plugins.skills.deps import check_skill_deps


class TestCheckSkillDeps:
    """Tests for check_skill_deps."""

    def test_empty_metadata_satisfied(self) -> None:
        """Empty metadata dict → all deps satisfied."""
        result = check_skill_deps({})
        assert result["satisfied"] is True
        assert result["missing_bins"] == []
        assert result["missing_env"] == []
        assert result["runtime"] in ("host", "docker")

    def test_bins_that_exist(self) -> None:
        """Requiring a binary that exists on PATH → satisfied."""
        metadata = {
            "openclaw": {
                "requires": {
                    "bins": ["python3"],
                },
            },
        }
        result = check_skill_deps(metadata)
        assert result["satisfied"] is True
        assert result["missing_bins"] == []

    def test_bins_that_dont_exist(self) -> None:
        """Requiring a binary that doesn't exist → missing_bins with name and hint."""
        metadata = {
            "openclaw": {
                "requires": {
                    "bins": ["nonexistent_binary_xyz_12345"],
                },
            },
        }
        result = check_skill_deps(metadata)
        assert result["satisfied"] is False
        assert len(result["missing_bins"]) == 1
        missing = result["missing_bins"][0]
        assert missing["name"] == "nonexistent_binary_xyz_12345"
        assert "hint" in missing
        assert isinstance(missing["hint"], str)
        assert len(missing["hint"]) > 0

    def test_env_vars_set_via_skill_env(self) -> None:
        """Env vars present in skill_env param → satisfied."""
        metadata = {
            "openclaw": {
                "requires": {
                    "env": ["MY_API_KEY"],
                },
            },
        }
        result = check_skill_deps(metadata, skill_env={"MY_API_KEY": "secret123"})
        assert result["satisfied"] is True
        assert result["missing_env"] == []

    def test_env_vars_not_set(self) -> None:
        """Env vars not in skill_env or os.environ → missing_env."""
        metadata = {
            "openclaw": {
                "requires": {
                    "env": ["TOTALLY_MISSING_VAR_ABC_999"],
                },
            },
        }
        # Make sure the var isn't in os.environ either
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TOTALLY_MISSING_VAR_ABC_999", None)
            result = check_skill_deps(metadata, skill_env={})
        assert result["satisfied"] is False
        assert "TOTALLY_MISSING_VAR_ABC_999" in result["missing_env"]

    def test_env_vars_from_os_environ(self) -> None:
        """Env vars present in os.environ (not skill_env) → satisfied."""
        metadata = {
            "openclaw": {
                "requires": {
                    "env": ["HOMECLAW_TEST_ENV_VAR"],
                },
            },
        }
        with patch.dict(os.environ, {"HOMECLAW_TEST_ENV_VAR": "hello"}):
            result = check_skill_deps(metadata, skill_env={})
        assert result["satisfied"] is True
        assert result["missing_env"] == []

    def test_nested_openclaw_requires_structure(self) -> None:
        """Full nested metadata.openclaw.requires with both bins and env."""
        metadata = {
            "openclaw": {
                "requires": {
                    "bins": ["python3"],
                    "env": ["HOMECLAW_NESTED_TEST_VAR"],
                },
            },
        }
        with patch.dict(os.environ, {"HOMECLAW_NESTED_TEST_VAR": "val"}):
            result = check_skill_deps(metadata)
        assert result["satisfied"] is True
        assert result["missing_bins"] == []
        assert result["missing_env"] == []

    def test_non_dict_openclaw_graceful(self) -> None:
        """Non-dict openclaw value → treated as satisfied (graceful)."""
        metadata = {"openclaw": "not a dict"}
        result = check_skill_deps(metadata)
        assert result["satisfied"] is True
        assert result["missing_bins"] == []
        assert result["missing_env"] == []

    def test_non_dict_requires_graceful(self) -> None:
        """Non-dict requires value → treated as satisfied."""
        metadata = {"openclaw": {"requires": "not a dict"}}
        result = check_skill_deps(metadata)
        assert result["satisfied"] is True

    def test_no_openclaw_key(self) -> None:
        """Metadata with other keys but no openclaw → satisfied."""
        metadata = {"name": "test-skill", "version": "1.0"}
        result = check_skill_deps(metadata)
        assert result["satisfied"] is True

    def test_multiple_missing_bins(self) -> None:
        """Multiple missing binaries are all reported."""
        metadata = {
            "openclaw": {
                "requires": {
                    "bins": [
                        "fake_bin_aaa_000",
                        "fake_bin_bbb_000",
                    ],
                },
            },
        }
        result = check_skill_deps(metadata)
        assert result["satisfied"] is False
        names = [b["name"] for b in result["missing_bins"]]
        assert "fake_bin_aaa_000" in names
        assert "fake_bin_bbb_000" in names

    def test_runtime_field_present(self) -> None:
        """Result always includes a runtime field (host or docker)."""
        result = check_skill_deps({})
        assert result["runtime"] in ("host", "docker")

    def test_mixed_bins_and_env_partial_failure(self) -> None:
        """Some deps met, some not → not satisfied."""
        metadata = {
            "openclaw": {
                "requires": {
                    "bins": ["python3", "nonexistent_zzz_999"],
                    "env": ["MISSING_ENV_VAR_XYZ_999"],
                },
            },
        }
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MISSING_ENV_VAR_XYZ_999", None)
            result = check_skill_deps(metadata)
        assert result["satisfied"] is False
        assert len(result["missing_bins"]) == 1
        assert result["missing_bins"][0]["name"] == "nonexistent_zzz_999"
        assert "MISSING_ENV_VAR_XYZ_999" in result["missing_env"]

    def test_skill_env_takes_precedence(self) -> None:
        """skill_env is checked before os.environ for env vars."""
        metadata = {
            "openclaw": {
                "requires": {
                    "env": ["DUAL_KEY"],
                },
            },
        }
        # Both in skill_env and os.environ — should satisfy via skill_env
        with patch.dict(os.environ, {"DUAL_KEY": "from_os"}):
            result = check_skill_deps(metadata, skill_env={"DUAL_KEY": "from_skill"})
        assert result["satisfied"] is True
