"""Interim-message heuristics — decide whether to surface LLM text mid-tool-chain."""

from __future__ import annotations

import re

# Minimum length for an interim message to be worth sending.
# Short filler like "Let me check" / "Un momento" / "ちょっと待って" are all
# under this threshold regardless of language.
_INTERIM_MIN_CHARS = 40

# Send a proactive progress message after this many consecutive silent tool
# rounds (no LLM-produced interim text). Keeps the user informed during
# long-running multi-step operations like bulk database writes.
PROGRESS_INTERVAL = 2

# Phrases that indicate the LLM is planning/deliberating, not addressing the user.
# When 3+ of these appear in a single interim block, it's a self-talk chain.
_SELF_TALK_RE = re.compile(
    r"\b(?:Let me|I need to|I'll |I should|Actually[,: ]|I'm going to"
    r"|I have to|I want to|Let's )\b",
    re.IGNORECASE,
)


def is_substantive_interim(text: str) -> bool:
    """Return True if the interim text is worth sending to the user."""
    if len(text) < _INTERIM_MIN_CHARS:
        return False
    # Suppress preamble that just introduces the next tool call
    if text.rstrip().endswith(":"):
        return False
    # Suppress LLM deliberation / self-talk chains (e.g. "Let me try...
    # Actually, I need to... I'll download... Actually, let me...")
    return len(_SELF_TALK_RE.findall(text)) < 3
