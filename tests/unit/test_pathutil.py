"""Tests for path safety utilities."""

import pytest

from homeclaw.pathutil import safe_date, safe_path_within, safe_slug


class TestSafeSlug:
    def test_normal_name(self) -> None:
        assert safe_slug("food") == "food"

    def test_spaces_to_hyphens(self) -> None:
        assert safe_slug("my topic") == "my-topic"

    def test_strips_traversal(self) -> None:
        assert safe_slug("../../etc/passwd") == "etcpasswd"

    def test_strips_slashes(self) -> None:
        assert safe_slug("path/to/file") == "pathtofile"

    def test_dots_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty after sanitization"):
            safe_slug("..")

    def test_preserves_hyphens_underscores(self) -> None:
        assert safe_slug("my-topic_v2") == "my-topic_v2"

    def test_lowercases(self) -> None:
        assert safe_slug("MyTopic") == "mytopic"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            safe_slug("")

    def test_only_special_chars_raises(self) -> None:
        with pytest.raises(ValueError):
            safe_slug("///...")


class TestSafeDate:
    def test_valid_date(self) -> None:
        assert safe_date("2026-03-19") == "2026-03-19"

    def test_traversal_rejected(self) -> None:
        with pytest.raises(ValueError):
            safe_date("../../etc/passwd")

    def test_partial_date_rejected(self) -> None:
        with pytest.raises(ValueError):
            safe_date("2026-03")

    def test_invalid_month_rejected(self) -> None:
        with pytest.raises(ValueError):
            safe_date("2026-13-01")


class TestSafePathWithin:
    def test_normal_path(self, tmp_path: pytest.TempPathFactory) -> None:
        base = tmp_path  # type: ignore[assignment]
        result = safe_path_within(base, "alice", "notes")  # type: ignore[arg-type]
        assert str(result).startswith(str(base))

    def test_traversal_rejected(self, tmp_path: pytest.TempPathFactory) -> None:
        base = tmp_path  # type: ignore[assignment]
        with pytest.raises(ValueError, match="escapes base"):
            safe_path_within(base, "..", "..", "etc", "passwd")  # type: ignore[arg-type]
