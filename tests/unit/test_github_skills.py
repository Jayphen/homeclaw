"""Tests for homeclaw/plugins/skills/github.py — URL parsing and multi-skill discovery."""

from __future__ import annotations

import pytest

from homeclaw.plugins.skills.github import (
    _GITHUB_ACTIONS,
    list_repo_skills,
    parse_github_url,
    raw_skill_md_url,
    skill_subpath_url,
)

# ---------------------------------------------------------------------------
# parse_github_url — subpath support
# ---------------------------------------------------------------------------


class TestParseGithubUrl:
    def test_repo_root(self) -> None:
        result = parse_github_url("https://github.com/user/repo")
        assert result == ("user", "repo", "main", "")

    def test_tree_branch(self) -> None:
        result = parse_github_url("https://github.com/user/repo/tree/dev")
        assert result == ("user", "repo", "dev", "")

    def test_tree_branch_with_subpath(self) -> None:
        result = parse_github_url(
            "https://github.com/user/repo/tree/main/skills/cooking"
        )
        assert result == ("user", "repo", "main", "skills/cooking")

    def test_bare_subpath_treated_as_path(self) -> None:
        """github.com/user/repo/skills/cooking → subpath, not ignored."""
        result = parse_github_url(
            "https://github.com/Jayphen/homeclaw/skills/some-skill"
        )
        assert result is not None
        user, repo, branch, subpath = result
        assert user == "Jayphen"
        assert repo == "homeclaw"
        assert branch == "main"
        assert subpath == "skills/some-skill"

    def test_bare_single_subpath(self) -> None:
        result = parse_github_url("https://github.com/user/repo/cooking")
        assert result == ("user", "repo", "main", "cooking")

    def test_github_actions_not_treated_as_subpath(self) -> None:
        """Known GitHub actions like 'issues', 'pulls' should not become subpaths."""
        for action in ("issues", "pulls", "actions", "settings", "wiki"):
            assert action in _GITHUB_ACTIONS
            result = parse_github_url(f"https://github.com/user/repo/{action}")
            assert result == ("user", "repo", "main", ""), (
                f"{action} should not be treated as subpath"
            )

    def test_raw_githubusercontent(self) -> None:
        # Note: raw.githubusercontent.com URLs retain the file path in subpath;
        # SKILL.md stripping only applies to the refs/heads/ case.
        result = parse_github_url(
            "https://raw.githubusercontent.com/user/repo/main/skills/cooking/SKILL.md"
        )
        assert result is not None
        user, repo, branch, subpath = result
        assert (user, repo, branch) == ("user", "repo", "main")
        # The subpath includes the filename for raw URLs
        assert subpath == "skills/cooking/SKILL.md"

    def test_non_github_returns_none(self) -> None:
        assert parse_github_url("https://example.com/foo/bar") is None


# ---------------------------------------------------------------------------
# raw_skill_md_url — includes subpath
# ---------------------------------------------------------------------------


class TestRawSkillMdUrl:
    def test_repo_root(self) -> None:
        url = raw_skill_md_url("https://github.com/user/repo")
        assert url == "https://raw.githubusercontent.com/user/repo/main/SKILL.md"

    def test_with_subpath(self) -> None:
        url = raw_skill_md_url(
            "https://github.com/user/repo/skills/cooking"
        )
        assert url == (
            "https://raw.githubusercontent.com/user/repo/main"
            "/skills/cooking/SKILL.md"
        )

    def test_tree_branch_subpath(self) -> None:
        url = raw_skill_md_url(
            "https://github.com/user/repo/tree/dev/skills/cooking"
        )
        assert url == (
            "https://raw.githubusercontent.com/user/repo/dev"
            "/skills/cooking/SKILL.md"
        )


# ---------------------------------------------------------------------------
# skill_subpath_url
# ---------------------------------------------------------------------------


class TestSkillSubpathUrl:
    def test_repo_root_plus_subpath(self) -> None:
        result = skill_subpath_url("https://github.com/user/repo", "cooking")
        assert result == "https://github.com/user/repo/tree/main/cooking"

    def test_existing_subpath_plus_extra(self) -> None:
        result = skill_subpath_url(
            "https://github.com/user/repo/skills", "cooking"
        )
        assert result == "https://github.com/user/repo/tree/main/skills/cooking"

    def test_non_github_raises(self) -> None:
        with pytest.raises(ValueError, match="Not a recognised"):
            skill_subpath_url("https://example.com/foo", "bar")


# ---------------------------------------------------------------------------
# list_repo_skills — mock the HTTP call
# ---------------------------------------------------------------------------


class TestListRepoSkills:
    @pytest.mark.anyio
    async def test_discovers_subdirectory_skills(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Finds SKILL.md files in subdirectories."""
        import httpx

        tree_response = {
            "tree": [
                {"path": "README.md", "type": "blob"},
                {"path": "cooking/SKILL.md", "type": "blob"},
                {"path": "cooking/scripts/fetch.sh", "type": "blob"},
                {"path": "weather/SKILL.md", "type": "blob"},
                {"path": "unrelated/file.py", "type": "blob"},
            ]
        }

        async def mock_get(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(200, json=tree_response)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        skills = await list_repo_skills("https://github.com/user/repo")
        paths = [s["path"] for s in skills]
        assert sorted(paths) == ["cooking", "weather"]

    @pytest.mark.anyio
    async def test_discovers_root_skill(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A SKILL.md at the repo root is also found (path='')."""
        import httpx

        tree_response = {
            "tree": [
                {"path": "SKILL.md", "type": "blob"},
                {"path": "scripts/run.sh", "type": "blob"},
            ]
        }

        async def mock_get(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(200, json=tree_response)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        skills = await list_repo_skills("https://github.com/user/repo")
        assert len(skills) == 1
        assert skills[0]["path"] == ""

    @pytest.mark.anyio
    async def test_scoped_to_subpath(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only returns skills under the specified subpath."""
        import httpx

        tree_response = {
            "tree": [
                {"path": "skills/cooking/SKILL.md", "type": "blob"},
                {"path": "skills/weather/SKILL.md", "type": "blob"},
                {"path": "other/tool/SKILL.md", "type": "blob"},
            ]
        }

        async def mock_get(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(200, json=tree_response)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        skills = await list_repo_skills("https://github.com/user/repo/skills")
        paths = [s["path"] for s in skills]
        assert sorted(paths) == ["cooking", "weather"]
        # The one under "other/" should NOT be included
        assert "other/tool" not in paths

    @pytest.mark.anyio
    async def test_non_github_returns_empty(self) -> None:
        skills = await list_repo_skills("https://example.com/foo")
        assert skills == []

    @pytest.mark.anyio
    async def test_api_failure_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        async def mock_get(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(404)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        skills = await list_repo_skills("https://github.com/user/repo")
        assert skills == []
