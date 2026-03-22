"""Integration tests for the Skills API routes (homeclaw/api/routes/skills.py)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from homeclaw.api.app import app
from homeclaw.api.deps import set_config, set_plugin_registry
from homeclaw.config import HomeclawConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SKILL_MD_TEMPLATE = """\
---
name: {name}
description: {description}
---

{instructions}
"""


def _create_skill(
    workspaces: Path,
    owner: str,
    name: str,
    description: str = "A test skill",
    instructions: str = "Do the thing.",
) -> Path:
    """Create a minimal skill directory with a SKILL.md file."""
    skill_dir = workspaces / owner / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        _SKILL_MD_TEMPLATE.format(
            name=name,
            description=description,
            instructions=instructions,
        )
    )
    return skill_dir


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workspaces(tmp_path: Path) -> Path:
    """Create a workspaces directory with household structure."""
    ws = tmp_path / "workspaces"
    (ws / "household").mkdir(parents=True)
    return ws


@pytest.fixture()
def _setup(workspaces: Path) -> Any:
    """Set up config with web_password="" (open access) and no plugin registry."""
    config = HomeclawConfig(workspaces_path=str(workspaces), web_password="")
    set_config(config)
    set_plugin_registry(None)
    yield
    set_plugin_registry(None)


@pytest.fixture()
def client(_setup: Any) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/skills — list skills
# ---------------------------------------------------------------------------


class TestListSkills:
    def test_empty_list(self, client: TestClient) -> None:
        """No skills → empty list."""
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert data["skills"] == []

    def test_lists_household_skill(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Household skill appears in the listing."""
        _create_skill(workspaces, "household", "weather", "Check the weather")

        resp = client.get("/api/skills")
        assert resp.status_code == 200
        skills = resp.json()["skills"]
        assert len(skills) == 1
        assert skills[0]["name"] == "weather"
        assert skills[0]["owner"] == "household"
        assert skills[0]["description"] == "Check the weather"

    def test_lists_multiple_skills(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Multiple skills across owners are listed."""
        _create_skill(workspaces, "household", "weather")
        _create_skill(workspaces, "household", "cooking")

        resp = client.get("/api/skills")
        assert resp.status_code == 200
        skills = resp.json()["skills"]
        assert len(skills) == 2
        names = {s["name"] for s in skills}
        assert names == {"weather", "cooking"}


# ---------------------------------------------------------------------------
# GET /api/skills/{owner}/{name} — skill detail
# ---------------------------------------------------------------------------


class TestGetSkill:
    def test_returns_skill_detail(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Skill detail includes metadata and file listing."""
        skill_dir = _create_skill(
            workspaces, "household", "weather",
            description="Check the weather",
            instructions="Use the weather API.",
        )
        # Add a data file
        data_dir = skill_dir / "data"
        data_dir.mkdir()
        (data_dir / "cache.json").write_text("{}")

        resp = client.get("/api/skills/household/weather")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "weather"
        assert data["owner"] == "household"
        assert data["description"] == "Check the weather"
        assert data["instructions"] == "Use the weather API."
        # Files should include SKILL.md and data/cache.json
        file_paths = [f["path"] for f in data["files"]]
        assert "SKILL.md" in file_paths
        assert any("cache.json" in p for p in file_paths)

    def test_not_found(self, client: TestClient) -> None:
        """Non-existent skill → 404."""
        resp = client.get("/api/skills/household/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/skills/{owner}/{name}/files/{path} — read file
# ---------------------------------------------------------------------------


class TestReadSkillFile:
    def test_read_skill_md(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Read the SKILL.md file content."""
        _create_skill(workspaces, "household", "weather")

        resp = client.get("/api/skills/household/weather/files/SKILL.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "SKILL.md"
        assert "weather" in data["content"]
        assert data["size"] > 0

    def test_read_nonexistent_file(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Reading a non-existent file → 404."""
        _create_skill(workspaces, "household", "weather")

        resp = client.get("/api/skills/household/weather/files/missing.txt")
        assert resp.status_code == 404

    def test_read_nonexistent_skill(self, client: TestClient) -> None:
        """Reading a file from a non-existent skill → 404."""
        resp = client.get("/api/skills/household/fake/files/SKILL.md")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/skills/{owner}/{name}/files/{path} — write file
# ---------------------------------------------------------------------------


class TestWriteSkillFile:
    def test_write_data_file(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Write a new data file inside the skill."""
        _create_skill(workspaces, "household", "weather")

        resp = client.put(
            "/api/skills/household/weather/files/data/test.md",
            json={"content": "# Test Data\nSome content."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "data/test.md"
        assert data["status"] == "written"
        assert data["size"] > 0

        # Verify file exists on disk
        file_path = workspaces / "household" / "skills" / "weather" / "data" / "test.md"
        assert file_path.is_file()
        assert file_path.read_text() == "# Test Data\nSome content."

    def test_write_creates_subdirectories(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Writing to a nested path creates intermediate directories."""
        _create_skill(workspaces, "household", "weather")

        resp = client.put(
            "/api/skills/household/weather/files/scripts/fetch.sh",
            json={"content": "#!/bin/bash\ncurl example.com"},
        )
        assert resp.status_code == 200

        file_path = workspaces / "household" / "skills" / "weather" / "scripts" / "fetch.sh"
        assert file_path.is_file()

    def test_write_nonexistent_skill(self, client: TestClient) -> None:
        """Writing to a non-existent skill → 404."""
        resp = client.put(
            "/api/skills/household/fake/files/data/test.md",
            json={"content": "test"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/skills/{owner}/{name}/files/{path} — delete file
# ---------------------------------------------------------------------------


class TestDeleteSkillFile:
    def test_delete_data_file(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Delete a data file from a skill."""
        skill_dir = _create_skill(workspaces, "household", "weather")
        data_dir = skill_dir / "data"
        data_dir.mkdir()
        data_file = data_dir / "test.md"
        data_file.write_text("delete me")

        resp = client.delete(
            "/api/skills/household/weather/files/data/test.md",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"
        assert data["path"] == "data/test.md"
        assert not data_file.exists()

    def test_delete_protected_skill_md(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Deleting SKILL.md is rejected (protected file)."""
        _create_skill(workspaces, "household", "weather")

        resp = client.delete(
            "/api/skills/household/weather/files/SKILL.md",
        )
        assert resp.status_code == 400
        assert "SKILL.md" in resp.json()["detail"]

    def test_delete_nonexistent_file(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Deleting a non-existent file → 404."""
        _create_skill(workspaces, "household", "weather")

        resp = client.delete(
            "/api/skills/household/weather/files/data/ghost.md",
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/skills/{owner}/{name} — archive skill
# ---------------------------------------------------------------------------


class TestDeleteSkill:
    def test_archives_skill(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Archiving a skill moves it to .archive/ with a timestamp suffix."""
        _create_skill(workspaces, "household", "weather")

        resp = client.delete("/api/skills/household/weather")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "archived"
        assert data["name"] == "weather"
        assert data["owner"] == "household"

        # Original dir should be gone
        original = workspaces / "household" / "skills" / "weather"
        assert not original.exists()

        # Archive should exist
        archive_root = workspaces / "household" / "skills" / ".archive"
        assert archive_root.is_dir()
        archived_dirs = list(archive_root.iterdir())
        assert len(archived_dirs) == 1
        assert archived_dirs[0].name.startswith("weather_")

    def test_archive_nonexistent_skill(self, client: TestClient) -> None:
        """Archiving a non-existent skill → 404."""
        resp = client.delete("/api/skills/household/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/skills/settings — read settings
# ---------------------------------------------------------------------------


class TestGetSkillSettings:
    def test_returns_settings(self, client: TestClient) -> None:
        """Returns current skill settings."""
        resp = client.get("/api/skills/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "skill_approval_required" in data
        assert "skill_allow_local_network" in data
        # Default values
        assert data["skill_approval_required"] is True
        assert data["skill_allow_local_network"] is False


# ---------------------------------------------------------------------------
# PUT /api/skills/settings — update settings
# ---------------------------------------------------------------------------


class TestUpdateSkillSettings:
    def test_updates_settings(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        """Update skill settings with new values."""
        # With web_password="" and no member_passwords, open access is granted
        # (including admin access) per the require_admin logic.
        resp = client.put(
            "/api/skills/settings",
            json={
                "skill_approval_required": False,
                "skill_allow_local_network": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["skill_approval_required"] is False
        assert data["skill_allow_local_network"] is True

    def test_partial_update(self, client: TestClient) -> None:
        """Partial update only changes specified fields."""
        resp = client.put(
            "/api/skills/settings",
            json={"skill_allow_local_network": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["skill_allow_local_network"] is True
        # approval_required should remain at its default
        assert data["skill_approval_required"] is True

    def test_empty_update(self, client: TestClient) -> None:
        """Empty update body leaves settings unchanged."""
        resp = client.put("/api/skills/settings", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["skill_approval_required"] is True
        assert data["skill_allow_local_network"] is False


# ---------------------------------------------------------------------------
# GET /api/skills/list-remote — discover skills in a repo
# ---------------------------------------------------------------------------


class TestListRemoteSkills:
    def test_rejects_non_github_url(self, client: TestClient) -> None:
        resp = client.get("/api/skills/list-remote", params={"url": "https://example.com/foo"})
        assert resp.status_code == 400
        assert "Not a recognised" in resp.json()["detail"]

    def test_lists_skills_in_repo(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Returns discovered skills from a GitHub repo."""
        from homeclaw.plugins.skills import github

        async def mock_list(url: str) -> list[dict[str, str]]:
            return [{"path": "cooking"}, {"path": "weather"}]

        monkeypatch.setattr(github, "list_repo_skills", mock_list)

        resp = client.get(
            "/api/skills/list-remote",
            params={"url": "https://github.com/user/skills-repo"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["skills"]) == 2
        paths = [s["path"] for s in data["skills"]]
        assert "cooking" in paths
        assert "weather" in paths


# ---------------------------------------------------------------------------
# POST /api/skills/install — multi-skill repo support
# ---------------------------------------------------------------------------


class TestInstallMultiSkill:
    def test_returns_skill_list_when_no_root_skill(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Multi-skill repo without install_all returns available skills."""
        import httpx

        from homeclaw.plugins.skills import github

        async def mock_get(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
            r = httpx.Response(404 if "SKILL.md" in str(url) else 200, json={})
            r._request = httpx.Request("GET", "https://fake")  # noqa: SLF001
            return r

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        async def mock_list(url: str) -> list[dict[str, str]]:
            return [{"path": "cooking"}, {"path": "weather"}]

        monkeypatch.setattr(github, "list_repo_skills", mock_list)

        resp = client.post(
            "/api/skills/install",
            json={"url": "https://github.com/user/skills-repo"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "multiple_skills"
        assert len(data["skills"]) == 2

    def test_install_all_installs_multiple(
        self, client: TestClient, workspaces: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """install_all=true installs all discovered skills."""
        import httpx

        from homeclaw.plugins.skills import github

        cooking_md = "---\nname: cooking\ndescription: Cook stuff\n---\nInstructions here"
        weather_md = "---\nname: weather\ndescription: Weather info\n---\nInstructions here"
        skill_contents = {
            "cooking": cooking_md,
            "weather": weather_md,
        }

        def _resp(status_code: int, **kwargs: Any) -> httpx.Response:
            """Build an httpx.Response with a dummy request attached."""
            r = httpx.Response(status_code, **kwargs)
            r._request = httpx.Request("GET", "https://fake")  # noqa: SLF001
            return r

        async def mock_get(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
            url_str = str(url)
            # Subpath SKILL.md → return content (check before root)
            for name, content in skill_contents.items():
                if f"/{name}/SKILL.md" in url_str:
                    return _resp(200, text=content)
            # Root SKILL.md (no skill subdir in path) → 404
            if url_str.endswith("/SKILL.md"):
                return _resp(404)
            # GitHub contents API for download_skill_repo
            return _resp(200, json=[])

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        async def mock_list(url: str) -> list[dict[str, str]]:
            return [{"path": "cooking"}, {"path": "weather"}]

        monkeypatch.setattr(github, "list_repo_skills", mock_list)

        resp = client.post(
            "/api/skills/install",
            json={
                "url": "https://github.com/user/skills-repo",
                "install_all": True,
            },
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["status"] == "installed_multiple"
        assert data["total"] == 2
        assert len(data["installed"]) == 2
        assert len(data["errors"]) == 0

        # Verify skills were written to disk
        assert (workspaces / "household" / "skills" / "cooking" / "SKILL.md").is_file()
        assert (workspaces / "household" / "skills" / "weather" / "SKILL.md").is_file()
