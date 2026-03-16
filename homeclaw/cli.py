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

        provider = create_provider(self.config)

        self.registry = ToolRegistry()
        if register_tools:
            register_builtin_tools(self.registry, self.workspaces)

        self.loop = AgentLoop(
            provider=provider,
            registry=self.registry,
            workspaces=self.workspaces,
            on_tool_call=on_tool_call,
            routing=self.config.routing,
        )

        self._scheduler: Scheduler | None = None

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
    )
    try:
        channel.run()
    finally:
        app.shutdown()
