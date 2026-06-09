"""Tests for system prompt guidance in homeclaw/agent/loop.py."""

from homeclaw.agent.prompts import build_system_prompt


def test_system_prompt_steers_interactive_skill_requests_toward_embedded_ui_apps() -> None:
    system, sections = build_system_prompt("", "normal")

    assert sections[0].name == "base_system_prompt"
    assert "prefer building it as an embedded skill mini-app" in system
    assert "`skill_enable_ui_app`" in system
    assert "`ui-app:`" in system
    # Sandbox model (TASK-29): source payload + host bridge, no iframe/CDN/token.
    assert "app/main.ts" in system
    assert "from 'homeclaw'" in system
    assert "@arrow-js/core" in system
    assert "https://cdn.jsdelivr.net/npm/@arrow-js/core/dist/index.mjs" not in system
    # The prompt steers AWAY from network/token (the data flows via the bridge).
    assert "never touch `localStorage`" in system
