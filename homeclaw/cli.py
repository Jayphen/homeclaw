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
    from homeclaw import HOUSEHOLD_WORKSPACE

    household = workspaces / HOUSEHOLD_WORKSPACE
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
        config: Any | None = None,
    ) -> None:
        from homeclaw.agent.loop import AgentLoop
        from homeclaw.agent.providers.factory import create_provider
        from homeclaw.agent.tools import ToolRegistry, register_builtin_tools
        from homeclaw.config import HomeclawConfig

        self.config = config or HomeclawConfig()
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

        from homeclaw.memory.semantic import SemanticMemory

        self._semantic_memory = SemanticMemory(str(self.workspaces))

        self.loop = AgentLoop(
            provider=provider,
            registry=self.registry,
            workspaces=self.workspaces,
            semantic_memory=self._semantic_memory,
            on_tool_call=on_tool_call,
            routing=self.config.routing,
        )

    async def initialize(self) -> None:
        """Async initialization — call after constructing in an event loop."""
        await self._semantic_memory.initialize()

    def _reload_routines(self) -> None:
        """Called by routine tools when ROUTINES.md changes."""
        if self._scheduler:
            self._scheduler.reload_routines()

    async def _notify_semantic_ready(self, message: str) -> None:
        """Called when the semantic index is built for the first time."""
        from homeclaw import HOUSEHOLD_WORKSPACE
        from homeclaw.agent.routing import CallType

        logger.info("Semantic memory ready — notifying household")
        await self.loop.run(
            f"[System notification] {message}",
            HOUSEHOLD_WORKSPACE,
            call_type=CallType.ROUTINE,
        )

    def load_scheduler(self) -> None:
        """Parse ROUTINES.md and register routines (does not start the event loop)."""
        from homeclaw.scheduler.scheduler import Scheduler

        self._scheduler = Scheduler(loop=self.loop, workspaces=self.workspaces)
        self._scheduler.load_routines_md()

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
        build_context(message="(dry run)", person=args.person.lower(), workspaces=workspaces),
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
        await app.initialize()
        app.start_scheduler()
        await run_repl(person=args.person.lower(), loop=app.loop, on_tool_call=_print_tool_call)

    try:
        asyncio.run(_chat())
    finally:
        app.shutdown()


def _run_serve(workspaces: Path, port: int) -> None:
    """Start the FastAPI server for the web UI and REST API.

    When TELEGRAM_TOKEN is configured, also starts the Telegram bot
    in the same process.
    """
    from homeclaw.api.app import app, set_config
    from homeclaw.api.deps import generate_setup_token
    from homeclaw.config import HomeclawConfig

    config = HomeclawConfig(workspaces_path=str(workspaces))
    set_config(config)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if not config.web_password:
        generate_setup_token()

    if config.telegram_token and config.is_provider_configured:
        _run_serve_with_telegram(app, config, workspaces, port)
    else:
        _run_serve_with_deferred_telegram(app, config, workspaces, port)


def _run_serve_with_telegram(
    app: Any, config: Any, workspaces: Path, port: int
) -> None:
    """Run uvicorn + Telegram bot concurrently in one event loop."""
    import uvicorn

    from homeclaw.channel.telegram import TelegramChannel

    hc_app = HomeclawApp(workspaces=workspaces, config=config)
    hc_app.load_scheduler()

    channel = TelegramChannel(
        token=config.telegram_token,
        loop=hc_app.loop,
        workspaces=workspaces,
        on_scheduler_start=hc_app.start_scheduler,
        allowed_user_ids=config.telegram_allowed_user_ids,
    )

    async def _serve() -> None:
        await hc_app.initialize()
        await channel.start()
        hc_app.start_scheduler()

        uv_config = uvicorn.Config(app, host="0.0.0.0", port=port)
        server = uvicorn.Server(uv_config)

        logger.info(
            "Starting web server on port %d + Telegram bot (workspaces: %s)",
            port, workspaces,
        )
        try:
            await server.serve()
        finally:
            await channel.stop()
            hc_app.shutdown()

    asyncio.run(_serve())


def _run_serve_with_deferred_telegram(
    app: Any, config: Any, workspaces: Path, port: int
) -> None:
    """Run uvicorn, starting Telegram later if configured via setup."""
    import asyncio as _asyncio

    import uvicorn

    from homeclaw.api.deps import set_on_telegram_configured
    from homeclaw.channel.telegram import TelegramChannel

    hc_app: HomeclawApp | None = None
    channel: TelegramChannel | None = None
    _telegram_lock = _asyncio.Lock()

    async def _start_telegram(token: str) -> None:
        nonlocal hc_app, channel
        async with _telegram_lock:
            if channel is not None:
                logger.info("Telegram bot already running, skipping")
                return
            try:
                hc_app = HomeclawApp(workspaces=workspaces, config=config)
            except ValueError:
                logger.warning("Cannot start Telegram bot — LLM provider not configured yet")
                return
            await hc_app.initialize()
            hc_app.load_scheduler()
            channel = TelegramChannel(
                token=token,
                loop=hc_app.loop,
                workspaces=workspaces,
                on_scheduler_start=hc_app.start_scheduler,
                allowed_user_ids=config.telegram_allowed_user_ids,
            )
            await channel.start()
            hc_app.start_scheduler()
            logger.info("Telegram bot started after setup")

    set_on_telegram_configured(_start_telegram)

    async def _serve() -> None:
        uv_config = uvicorn.Config(app, host="0.0.0.0", port=port)
        server = uvicorn.Server(uv_config)
        logger.info("Starting web server on port %d (workspaces: %s)", port, workspaces)
        try:
            await server.serve()
        finally:
            if channel:
                await channel.stop()
            if hc_app:
                hc_app.shutdown()

    asyncio.run(_serve())


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
