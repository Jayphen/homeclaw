#!/usr/bin/env python3
"""Create or reset workspaces-dev/ to a deterministic known state.

Run:  python scripts/setup_dev_fixtures.py
      make dev-setup

No API keys required.  Idempotent — deletes and recreates workspaces-dev/ each
time.  Uses fixed timestamps so the output is identical across runs.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "workspaces-dev"

# ===================================================================
# Fixture data
# ===================================================================

CONFIG = {
    "anthropic_api_key": "SET_ANTHROPIC_API_KEY_ENV_VAR",
    "telegram_token": "SET_TELEGRAM_TOKEN_ENV_VAR",
    "web_password": "devpassword",
    "workspaces_path": "./workspaces-dev",
}

SARAH_CHEN = {
    "id": "sarah-chen",
    "name": "Sarah Chen",
    "nicknames": [],
    "relationship": "friend",
    "birthday": None,
    "interactions": [
        {
            "date": "2026-01-20T15:30:00Z",
            "type": "meetup",
            "notes": "Brunch in Park Slope, talked about her new design system project",
        },
        {
            "date": "2025-12-15T18:00:00Z",
            "type": "call",
            "notes": "Caught up on holiday plans, she's visiting family in Vancouver",
        },
        {
            "date": "2025-11-08T12:00:00Z",
            "type": "message",
            "notes": "Shared article about design tools, she recommended a podcast",
        },
    ],
    "reminders": [
        {"interval_days": 30, "next_date": "2026-02-19", "note": "Monthly catch-up"}
    ],
    "last_contact": "2026-01-20T15:30:00Z",
}

JAMES_KO = {
    "id": "james-ko",
    "name": "James Ko",
    "nicknames": ["Jim", "Jimmy"],
    "relationship": "colleague",
    "birthday": "1990-03-22",
    "interactions": [
        {
            "date": "2026-03-01T10:00:00Z",
            "type": "meetup",
            "notes": "Lunch after sprint retro, discussed the new microservice architecture",
        }
    ],
    "reminders": [],
    "last_contact": "2026-03-01T10:00:00Z",
}

GRANDMA_ELEANOR = {
    "id": "grandma-eleanor",
    "name": "Eleanor",
    "nicknames": ["Grandma", "Nana", "Gran"],
    "relationship": "family",
    "birthday": "1948-06-15",
    "interactions": [
        {
            "date": "2026-02-20T14:00:00Z",
            "type": "call",
            "notes": "Weekly check-in, she mentioned her tomato seedlings are sprouting",
        },
        {
            "date": "2026-01-10T11:00:00Z",
            "type": "call",
            "notes": "New Year catch-up, talked about her book club pick for January",
        },
    ],
    "reminders": [
        {
            "interval_days": 14,
            "next_date": "2026-03-06",
            "note": "Bi-weekly check-in call",
        }
    ],
    "last_contact": "2026-02-20T14:00:00Z",
}

ALICE_MEMORY_PERSONAL = """\
# personal

- [2026-03-10 09:00] Vegetarian
- [2026-03-10 09:00] Works Monday-Friday 9-5 at a marketing agency
- [2026-03-10 09:00] Prefers morning reminders before 8am
- [2026-03-10 09:00] Has a cat named Mochi
"""

ALICE_MEMORY_PREFS = """\
# preferences

- [2026-03-10 09:00] Reminder time: 7:30am
- [2026-03-10 09:00] Communication style: brief and friendly
- [2026-03-10 09:00] Dietary: vegetarian
"""

BOB_MEMORY_PERSONAL = """\
# personal

- [2026-03-10 12:00] Runs on weekends, usually Saturday morning
- [2026-03-10 12:00] Enjoys cooking, especially Italian food
- [2026-03-10 12:00] Managing the kitchen renovation project
- [2026-03-10 12:00] Works from home as a software engineer
"""

BOB_MEMORY_PREFS = """\
# preferences

- [2026-03-10 12:00] Reminder time: 8:00am
- [2026-03-10 12:00] Communication style: detailed and thorough
"""

CONTACT_NOTES = {
    "sarah-chen": """\
# Sarah Chen

- [2025-11-08 12:00] Lives in Brooklyn
- [2025-11-08 12:00] Works as a UX designer at Figma
- [2025-11-08 12:00] Has a golden retriever named Pixel
- [2025-12-15 18:00] Allergic to shellfish
""",
    "james-ko": """\
# James Ko

- [2026-03-01 10:00] Team lead on the backend team
- [2026-03-01 10:00] Into rock climbing
""",
    "grandma-eleanor": """\
# Eleanor

- [2026-01-10 11:00] Lives in Portland
- [2026-01-10 11:00] Loves gardening
- [2026-01-10 11:00] Has a cat named Whiskers
- [2026-02-20 14:00] Takes medication at 8am and 8pm
""",
}

# History — clean baseline with realistic exchanges (user/assistant only)
ALICE_HISTORY = [
    {"role": "user", "content": "What's on my plate today?"},
    {"role": "assistant", "content": "Good morning! Here's your Monday overview: You have work 9-5 as usual. Eleanor's bi-weekly check-in is overdue (was due March 6). Sarah Chen's monthly catch-up is also overdue. Mochi probably needs feeding. Want me to help you plan anything?"},
    {"role": "user", "content": "Can you remind me to buy cat food on Saturday?"},
    {"role": "assistant", "content": "Done! I've set a reminder for Saturday March 21 to buy cat food. You'll get it at 7:30am as usual."},
    {"role": "user", "content": "What do you know about James?"},
    {"role": "assistant", "content": "James Ko is a colleague — team lead on the backend team, and he's into rock climbing. You last caught up on March 1st over lunch after a sprint retro. His birthday is coming up on March 22nd, just 6 days away! Want me to set a reminder to get him something?"},
    {"role": "user", "content": "Yeah good idea, remind me the day before"},
    {"role": "assistant", "content": "Set! You'll get a reminder on March 21 to sort a birthday gift for James. Given he's into rock climbing, maybe a chalk bag or a day pass to a climbing gym?"},
    {"role": "user", "content": "What's the latest household note?"},
    {"role": "assistant", "content": "The most recent note is from March 14: \"Alice has dentist appointment Thursday 10am.\" Before that, on March 10: you and Bob discussed the kitchen renovation — he wants new countertops and you'd prefer to keep costs under $3k."},
]

BOB_HISTORY = [
    {"role": "user", "content": "What's the latest on the kitchen renovation?"},
    {"role": "assistant", "content": "Based on the household note from March 10th: you and Alice discussed countertops. You'd like new ones, and Alice wants to keep the total budget under $3k. No contractor quotes logged yet — want me to create a task to research countertop options and pricing?"},
    {"role": "user", "content": "What should I cook for dinner tonight? Something Italian."},
    {"role": "assistant", "content": "How about a classic cacio e pepe? You probably have pasta, pecorino, and black pepper on hand. It's quick (20 minutes) and pairs well with a simple side salad. Just remember Alice is vegetarian, so no pancetta additions — cacio e pepe is naturally veggie-friendly."},
    {"role": "user", "content": "Any birthdays coming up I should know about?"},
    {"role": "assistant", "content": "Yes — James Ko's birthday is March 22nd, that's 6 days away. He's into rock climbing, so maybe a gift card to a climbing gym? Grandma Eleanor's birthday isn't until June 15th, so you have time there."},
]

PLANTS = [
    {
        "name": "Monstera",
        "location": "Living room",
        "water_interval_days": 7,
        "last_watered": "2026-03-10",
        "notes": "Likes indirect light",
    },
    {
        "name": "Snake Plant",
        "location": "Bedroom",
        "water_interval_days": 14,
        "last_watered": "2026-03-05",
        "notes": "Very low maintenance",
    },
    {
        "name": "Basil",
        "location": "Kitchen windowsill",
        "water_interval_days": 2,
        "last_watered": "2026-03-13",
        "notes": "Needs frequent watering, harvest leaves regularly",
    },
]

HOUSEHOLD_NOTE_0310 = (
    "Discussed kitchen renovation. Bob wants new countertops."
    " Alice prefers keeping cost under $3k.\n"
)
HOUSEHOLD_NOTE_0314 = "Alice has dentist appointment Thursday 10am.\n"

ROUTINES_MD = """\
# Household Routines

## Morning briefing
- **Schedule**: Every weekday at 7:30am
- **Action**: Send each household member their daily summary

## Weekly grocery check
- **Schedule**: Every Sunday at 10:00am
- **Action**: Review pantry notes and suggest a grocery list

## Plant watering check
- **Schedule**: Every 3 days
- **Action**: Check plant watering schedule and remind if any are overdue

## Contact check-in
- **Schedule**: Every Monday at 9:00am
- **Action**: Review contacts for overdue check-ins and suggest reaching out
"""

ALICE_NOTE_0312 = "Need to call Mum about Easter.\n"

PLANTS_PLUGIN_PY = '''\
"""Plants plugin — reference implementation. See plugins/plants/ in the main repo."""
# TODO: Implement once plugin loader is built (homeclaw-jzg)
'''

# Sample cost log entries — realistic mix of conversations and routines
_HAIKU = "claude-haiku-4-5-20251001"
_SONNET = "claude-sonnet-4-6"


def _cost(
    ts: str, ct: str, model: str, inp: int,
    out: int, cached: int, cost: float, person: str,
) -> dict:
    return {
        "ts": ts, "call_type": ct, "model": model,
        "input_tokens": inp, "output_tokens": out,
        "cached_tokens": cached, "estimated_cost_usd": cost,
        "person": person,
    }


COST_LOG_ENTRIES = [
    _cost("2026-03-10T08:00:00+00:00", "routine", _HAIKU, 820, 150, 600, 0.000824, "household"),
    _cost("2026-03-10T09:15:00+00:00", "conversation", _SONNET, 1842, 203, 1200, 0.004986, "alice"),
    _cost("2026-03-10T12:30:00+00:00", "conversation", _SONNET, 2100, 310, 1500, 0.006750, "bob"),
    _cost("2026-03-10T20:00:00+00:00", "routine", _HAIKU, 750, 120, 500, 0.000720, "household"),
    _cost("2026-03-11T07:30:00+00:00", "routine", _HAIKU, 830, 180, 600, 0.000952, "household"),
    _cost("2026-03-11T10:00:00+00:00", "conversation", _SONNET, 1650, 250, 1100, 0.005550, "alice"),
    _cost("2026-03-12T07:30:00+00:00", "routine", _HAIKU, 810, 160, 580, 0.000870, "household"),
    _cost("2026-03-12T14:00:00+00:00", "conversation", _SONNET, 1920, 280, 1300, 0.006460, "alice"),
    _cost("2026-03-13T07:30:00+00:00", "routine", _HAIKU, 840, 170, 610, 0.000912, "household"),
    _cost("2026-03-13T18:00:00+00:00", "conversation", _SONNET, 2200, 350, 1600, 0.007350, "bob"),
    _cost("2026-03-14T07:30:00+00:00", "routine", _HAIKU, 825, 155, 590, 0.000845, "household"),
    _cost("2026-03-14T11:00:00+00:00", "conversation", _SONNET, 1780, 220, 1200, 0.005340, "alice"),
    _cost("2026-03-15T07:30:00+00:00", "routine", _HAIKU, 835, 165, 600, 0.000882, "household"),
    _cost("2026-03-15T16:00:00+00:00", "conversation", _SONNET, 1950, 290, 1350, 0.006450, "bob"),
    _cost("2026-03-16T07:30:00+00:00", "routine", _HAIKU, 820, 150, 600, 0.000824, "household"),
]


# ===================================================================
# Write files
# ===================================================================


def _json(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def _jsonl(entries: list[dict]) -> str:
    return "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n"


def _build_manifest() -> list[tuple[Path, str]]:
    return [
        (Path("config.json"), _json(CONFIG)),
        (Path("household/contacts/sarah-chen.json"), _json(SARAH_CHEN)),
        (Path("household/contacts/james-ko.json"), _json(JAMES_KO)),
        (Path("household/contacts/grandma-eleanor.json"), _json(GRANDMA_ELEANOR)),
        (Path("household/notes/2026-03-10.md"), HOUSEHOLD_NOTE_0310),
        (Path("household/notes/2026-03-14.md"), HOUSEHOLD_NOTE_0314),
        (Path("household/ROUTINES.md"), ROUTINES_MD),
        (Path("alice/memory/personal.md"), ALICE_MEMORY_PERSONAL),
        (Path("alice/memory/preferences.md"), ALICE_MEMORY_PREFS),
        (Path("alice/history.jsonl"), _jsonl(ALICE_HISTORY)),
        (Path("alice/notes/2026-03-12.md"), ALICE_NOTE_0312),
        (Path("bob/memory/personal.md"), BOB_MEMORY_PERSONAL),
        (Path("bob/memory/preferences.md"), BOB_MEMORY_PREFS),
        (Path("bob/history.jsonl"), _jsonl(BOB_HISTORY)),
        *[
            (Path(f"household/contacts/notes/{cid}.md"), content)
            for cid, content in CONTACT_NOTES.items()
        ],
        (Path("plugins/plants/plants.json"), _json(PLANTS)),
        (Path("plugins/plants/plugin.py"), PLANTS_PLUGIN_PY),
        (Path("cost_log.jsonl"), _jsonl(COST_LOG_ENTRIES)),
    ]


def main() -> None:
    print(f"Target directory: {WORKSPACE}")

    if WORKSPACE.exists():
        print("  Removing existing workspaces-dev/ ...")
        shutil.rmtree(WORKSPACE)

    manifest = _build_manifest()
    for rel_path, content in manifest:
        full_path = WORKSPACE / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        print(f"  wrote {rel_path}")

    print(f"\nDone — {len(manifest)} files created in workspaces-dev/")


if __name__ == "__main__":
    main()
