"""CLI entry point — ``homeclaw`` starts the household assistant."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeclaw.scheduler.scheduler import Scheduler

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="homeclaw", description="homeclaw household AI assistant")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("telegram", help="Start the Telegram bot")

    serve = sub.add_parser("serve", help="Start the web UI and API server")
    serve.add_argument("--workspaces", default="./workspaces", help="Path to workspaces directory")
    serve.add_argument("--port", type=int, default=8080, help="Port to listen on")

    chat = sub.add_parser("chat", help="Start an interactive chat session")
    chat.add_argument("--person", required=True, help="Household member name")
    chat.add_argument("--workspaces", default="./workspaces", help="Path to workspaces directory")
    chat.add_argument(
        "--no-tools",
        action="store_true",
        help="Skip tool registration (LLM-only mode)",
    )
    chat.add_argument(
        "--dry-run",
        action="store_true",
        help="Print system prompt and tools, then exit",
    )

    return parser


def _print_tool_call(name: str, args: dict[str, Any]) -> None:
    print(f"[tool] {name}: {json.dumps(args)}")


_DEFAULT_ROUTINES_MD = """\
# Household Routines

## Morning briefing
- **Schedule**: Every weekday at 7:30am
- **Action**: Send each household member their daily summary

## Contact check-in
- **Schedule**: Every Monday at 9:00am
- **Action**: Review contacts for overdue check-ins and suggest reaching out
"""


def _ensure_default_files(workspaces: Path) -> None:
    """Seed default files into a fresh workspaces directory."""
    household = workspaces / "household"
    household.mkdir(parents=True, exist_ok=True)
    routines = household / "ROUTINES.md"
    if not routines.exists():
        routines.write_text(_DEFAULT_ROUTINES_MD)
        logger.info("Seeded default %s", routines)


class HomeclawApp:
    """Shared application core — config, provider, agent loop, and scheduler.

    Any channel (Telegram, REPL, web UI, Slack, etc.) uses this to get a
    configured AgentLoop. The scheduler runs exactly once regardless of
    which channels are active.
    """

    def __init__(
        self,
        workspaces: Path | None = None,
        register_tools: bool = True,
        on_tool_call: Any | None = _print_tool_call,
    ) -> None:
        from homeclaw.agent.loop import AgentLoop
        from homeclaw.agent.providers.factory import create_provider
        from homeclaw.agent.tools import ToolRegistry, register_builtin_tools
        from homeclaw.config import HomeclawConfig

        self.config = HomeclawConfig()
        self.workspaces = (workspaces or self.config.workspaces).resolve()
        _ensure_default_files(self.workspaces)

        provider = create_provider(self.config)

        self._scheduler: Scheduler | None = None

        self.registry = ToolRegistry()
        if register_tools:
            register_builtin_tools(
                self.registry,
                self.workspaces,
                on_routines_changed=self._reload_routines,
                config=self.config,
                on_semantic_ready=self._notify_semantic_ready,
            )

        self.loop = AgentLoop(
            provider=provider,
            registry=self.registry,
            workspaces=self.workspaces,
            on_tool_call=on_tool_call,
            routing=self.config.routing,
        )

    def _reload_routines(self) -> None:
        """Called by routine tools when ROUTINES.md changes."""
        if self._scheduler:
            self._scheduler.reload_routines()

    async def _notify_semantic_ready(self, message: str) -> None:
        """Called when the semantic index is built for the first time."""
        from homeclaw.agent.routing import CallType

        logger.info("Semantic memory ready — notifying household")
        await self.loop.run(
            f"[System notification] {message}",
            "household",
            call_type=CallType.ROUTINE,
        )

    def load_scheduler(self) -> None:
        """Parse ROUTINES.md and register routines (does not start the event loop)."""
        from homeclaw.scheduler.scheduler import Scheduler

        self._scheduler = Scheduler(loop=self.loop, workspaces=self.workspaces)
        count = self._scheduler.load_routines_md()
        if count == 0:
            self._scheduler = None

    def start_scheduler(self) -> None:
        """Start the scheduler. Must be called inside a running event loop."""
        if self._scheduler:
            self._scheduler.start()

    def shutdown(self) -> None:
        """Shut down background services."""
        if self._scheduler:
            self._scheduler.shutdown()

    @property
    def scheduler(self) -> Scheduler | None:
        return self._scheduler


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "telegram":
        _run_telegram()
        return

    if args.command == "serve":
        _run_serve(Path(args.workspaces).resolve(), args.port)
        return

    if args.command != "chat":
        parser.print_help()
        sys.exit(1)

    workspaces = Path(args.workspaces).resolve()

    if args.dry_run:
        _dry_run(workspaces, args)
        return

    _run_chat(workspaces, args)


def _dry_run(workspaces: Path, args: argparse.Namespace) -> None:
    """Print the full system prompt and registered tools, then exit."""
    from homeclaw.agent.context import build_context
    from homeclaw.agent.loop import SYSTEM_PROMPT
    from homeclaw.agent.tools import ToolRegistry, register_builtin_tools

    context = asyncio.run(
        build_context(message="(dry run)", person=args.person, workspaces=workspaces),
    )
    system = SYSTEM_PROMPT.format(context=context)

    print("=== System Prompt ===")
    print(system)
    print()

    if not args.no_tools:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspaces)
        definitions = registry.get_definitions()
        print(f"=== Tools ({len(definitions)}) ===")
        for td in definitions:
            print(f"  {td.name}: {td.description}")
        print()
    else:
        print("=== Tools: disabled (--no-tools) ===\n")


def _run_chat(workspaces: Path, args: argparse.Namespace) -> None:
    """Load config, create provider + loop, and start the REPL."""
    from homeclaw.channel.repl import run_repl

    app = HomeclawApp(workspaces=workspaces, register_tools=not args.no_tools)
    app.load_scheduler()

    async def _chat() -> None:
        app.start_scheduler()
        await run_repl(person=args.person, loop=app.loop, on_tool_call=_print_tool_call)

    try:
        asyncio.run(_chat())
    finally:
        app.shutdown()


def _run_serve(workspaces: Path, port: int) -> None:
    """Start the FastAPI server for the web UI and REST API."""
    import uvicorn

    from homeclaw.api.app import app, set_config
    from homeclaw.config import HomeclawConfig

    config = HomeclawConfig(workspaces_path=str(workspaces))
    set_config(config)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logger.info("Starting web server on port %d (workspaces: %s)", port, workspaces)
    uvicorn.run(app, host="0.0.0.0", port=port)


def _run_telegram() -> None:
    """Load config, create provider + loop, and start the Telegram bot."""
    from homeclaw.channel.telegram import TelegramChannel

    app = HomeclawApp()

    if not app.config.telegram_token:
        print("Error: TELEGRAM_TOKEN not set. Set it in .env or as an environment variable.")
        sys.exit(1)

    app.load_scheduler()

    channel = TelegramChannel(
        token=app.config.telegram_token,
        loop=app.loop,
        workspaces=app.workspaces,
        on_scheduler_start=app.start_scheduler,
        allowed_user_ids=app.config.telegram_allowed_user_ids,
    )
    try:
        channel.run()
    finally:
        app.shutdown()
