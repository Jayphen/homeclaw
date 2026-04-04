"""Tests for system prompt guidance in homeclaw/agent/loop.py."""

from homeclaw.agent.loop import _build_system_prompt


def test_system_prompt_steers_interactive_skill_requests_toward_embedded_ui_apps() -> None:
    system, sections = _build_system_prompt("", "normal")

    assert sections[0].name == "base_system_prompt"
    assert "prefer building it as an embedded skill mini-app" in system
    assert "`skill_enable_ui_app`" in system
    assert "`skill_read_file`/`skill_write_file`/`skill_replace_in_file`" in system
    assert "`memory_list_topics` or `memory_read_topic`" in system
    assert "`contact_create`" in system
    assert "`ui-app:`" in system
    assert "`assets/index.html`" in system
    assert "Arrow.js" in system
    assert "https://cdn.jsdelivr.net/npm/@arrow-js/core/dist/index.mjs" in system
    assert "localStorage.getItem('homeclaw_token')" in system
