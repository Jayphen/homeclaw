"""CLI entry point — ``homeclaw`` starts the household assistant."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
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
    sub.add_parser("whatsapp", help="Start the WhatsApp bot (requires homeclaw[whatsapp])")

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

        from homeclaw.channel.dispatcher import ChannelDispatcher
        from homeclaw.plugins.loader import load_all_plugins
        from homeclaw.plugins.registry import PluginRegistry
        from homeclaw.plugins.skills.loader import load_all_skills

        self.dispatcher = ChannelDispatcher(self.workspaces)
        self.registry = ToolRegistry()
        self.plugin_registry = PluginRegistry(tool_registry=self.registry)

        # Load household-wide skills at startup (private skills hot-loaded on skill_create)
        load_all_skills(self.workspaces, "household", self.plugin_registry)

        # Load user-installed Python plugins (disabled by default, opt-in via enabled.json)
        load_all_plugins(self.workspaces / "plugins", self.plugin_registry)

        if register_tools:
            register_builtin_tools(
                self.registry,
                self.workspaces,
                on_routines_changed=self._reload_routines,
                config=self.config,
                plugin_registry=self.plugin_registry,
                dispatcher=self.dispatcher,
            )

        from homeclaw.memory.semantic import SemanticMemory

        # Use OpenAI embeddings only with a real OpenAI key (sk-..., not sk-or-v1).
        _key = self.config.openai_api_key or ""
        _is_openai_key = _key.startswith("sk-") and not _key.startswith("sk-or-")
        embedding_provider = "openai" if _is_openai_key else "local"
        self._semantic_memory = SemanticMemory(
            str(self.workspaces),
            embedding_provider=embedding_provider,
            embedding_api_key=self.config.openai_api_key,
        )

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
        self._semantic_memory.stop()
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

    if args.command == "whatsapp":
        _run_whatsapp()
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

    from homeclaw.api.logbuffer import install_log_buffer
    install_log_buffer()

    if not config.web_password:
        generate_setup_token()

    if config.telegram_token and config.is_provider_configured:
        _run_serve_with_channels(app, config, workspaces, port)
    else:
        _run_serve_with_deferred_telegram(app, config, workspaces, port)


def _run_serve_with_channels(
    app: Any, config: Any, workspaces: Path, port: int
) -> None:
    """Run uvicorn + Telegram (and optionally WhatsApp) concurrently in one event loop."""
    import uvicorn

    from homeclaw.channel.telegram import TelegramChannel

    hc_app = HomeclawApp(workspaces=workspaces, config=config)
    from homeclaw.api.deps import set_plugin_registry
    set_plugin_registry(hc_app.plugin_registry)
    hc_app.load_scheduler()

    tg_channel = TelegramChannel(
        token=config.telegram_token,
        loop=hc_app.loop,
        workspaces=workspaces,
        on_scheduler_start=hc_app.start_scheduler,
        allowed_user_ids=config.telegram_allowed_user_ids,
        dispatcher=hc_app.dispatcher,
    )

    wa_channel = None
    if config.whatsapp_enabled:
        try:
            from homeclaw.channel.whatsapp import WhatsAppChannel
            wa_channel = WhatsAppChannel(
                loop=hc_app.loop,
                workspaces=workspaces,
                allowed_phones=config.whatsapp_allowed_phone_numbers,
                dispatcher=hc_app.dispatcher,
                phone_number=config.whatsapp_phone_number,
            )
        except ImportError:
            logger.warning(
                "whatsapp_enabled=true but neonize is not installed; "
                "install with: pip install homeclaw[whatsapp]"
            )

    async def _serve() -> None:
        await hc_app.initialize()
        await tg_channel.start()
        if wa_channel:
            await wa_channel.start()
            from homeclaw.api.deps import set_whatsapp_connected_fn, set_whatsapp_qr_fn
            _wa = wa_channel  # capture for lambda
            set_whatsapp_connected_fn(lambda: _wa.connected)
            set_whatsapp_qr_fn(lambda: _wa.pending_qr)
        hc_app.start_scheduler()

        uv_config = uvicorn.Config(app, host="0.0.0.0", port=port)
        server = uvicorn.Server(uv_config)

        channels_desc = "Telegram" + (" + WhatsApp" if wa_channel else "")
        logger.info(
            "Starting web server on port %d + %s (workspaces: %s)",
            port, channels_desc, workspaces,
        )
        try:
            await server.serve()
        finally:
            await tg_channel.stop()
            if wa_channel:
                await wa_channel.stop()
            hc_app.shutdown()

    asyncio.run(_serve())


def _run_serve_with_deferred_telegram(
    app: Any, config: Any, workspaces: Path, port: int
) -> None:
    """Run uvicorn, starting Telegram later if configured via setup.

    WhatsApp (if enabled) starts immediately since it needs no token.
    """
    import asyncio as _asyncio

    import uvicorn

    from homeclaw.api.deps import set_on_telegram_configured
    from homeclaw.channel.telegram import TelegramChannel

    hc_app: HomeclawApp | None = None
    hc_app_ready: bool = False  # True once initialize()+load_scheduler() have run
    tg_channel: TelegramChannel | None = None
    _telegram_lock = _asyncio.Lock()

    # WhatsApp can start right away — no token needed, just a DB file.
    wa_channel = None
    if config.whatsapp_enabled and config.is_provider_configured:
        try:
            from homeclaw.channel.whatsapp import WhatsAppChannel
            hc_app = HomeclawApp(workspaces=workspaces, config=config)
            from homeclaw.api.deps import set_plugin_registry as _set_pr
            _set_pr(hc_app.plugin_registry)
            wa_channel = WhatsAppChannel(
                loop=hc_app.loop,
                workspaces=workspaces,
                allowed_phones=config.whatsapp_allowed_phone_numbers,
                dispatcher=hc_app.dispatcher,
                phone_number=config.whatsapp_phone_number,
            )
        except ImportError:
            logger.warning(
                "whatsapp_enabled=true but neonize is not installed; "
                "install with: pip install homeclaw[whatsapp]"
            )

    async def _start_telegram(token: str) -> None:
        nonlocal hc_app, hc_app_ready, tg_channel
        async with _telegram_lock:
            if tg_channel is not None:
                logger.info("Telegram bot already running, skipping")
                return
            try:
                if hc_app is None:
                    hc_app = HomeclawApp(workspaces=workspaces, config=config)
                    from homeclaw.api.deps import set_plugin_registry
                    set_plugin_registry(hc_app.plugin_registry)
            except ValueError:
                logger.warning("Cannot start Telegram bot — LLM provider not configured yet")
                return
            if not hc_app_ready:
                await hc_app.initialize()
                hc_app.load_scheduler()
                hc_app_ready = True
            tg_channel = TelegramChannel(
                token=token,
                loop=hc_app.loop,
                workspaces=workspaces,
                on_scheduler_start=hc_app.start_scheduler,
                allowed_user_ids=config.telegram_allowed_user_ids,
                dispatcher=hc_app.dispatcher,
            )
            await tg_channel.start()
            hc_app.start_scheduler()
            logger.info("Telegram bot started after setup")

    set_on_telegram_configured(_start_telegram)

    async def _serve() -> None:
        nonlocal hc_app_ready
        if wa_channel and hc_app:
            await hc_app.initialize()
            await wa_channel.start()
            from homeclaw.api.deps import set_whatsapp_connected_fn, set_whatsapp_qr_fn
            _wa = wa_channel  # capture for lambda
            set_whatsapp_connected_fn(lambda: _wa.connected)  # type: ignore[union-attr]
            set_whatsapp_qr_fn(lambda: _wa.pending_qr)  # type: ignore[union-attr]
            hc_app.load_scheduler()
            hc_app.start_scheduler()
            hc_app_ready = True

        uv_config = uvicorn.Config(app, host="0.0.0.0", port=port)
        server = uvicorn.Server(uv_config)
        logger.info("Starting web server on port %d (workspaces: %s)", port, workspaces)
        try:
            await server.serve()
        finally:
            if tg_channel:
                await tg_channel.stop()
            if wa_channel:
                await wa_channel.stop()
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
        dispatcher=app.dispatcher,
    )
    try:
        channel.run()
    finally:
        app.shutdown()


def _run_whatsapp() -> None:
    """Load config, create provider + loop, and start the WhatsApp bot."""
    try:
        from homeclaw.channel.whatsapp import WhatsAppChannel
    except ImportError:
        print(
            "Error: neonize is not installed. "
            "Install WhatsApp support with: pip install homeclaw[whatsapp]"
        )
        sys.exit(1)

    app = HomeclawApp()
    app.load_scheduler()

    channel = WhatsAppChannel(
        loop=app.loop,
        workspaces=app.workspaces,
        allowed_phones=app.config.whatsapp_allowed_phone_numbers,
        dispatcher=app.dispatcher,
        phone_number=app.config.whatsapp_phone_number,
    )

    async def _run() -> None:
        await app.initialize()
        await channel.start()
        app.start_scheduler()
        logger.info("WhatsApp bot running — press Ctrl+C to stop")
        try:
            # Wait until interrupted
            await asyncio.get_running_loop().create_future()
        except asyncio.CancelledError:
            pass
        finally:
            await channel.stop()
            app.shutdown()

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_run())
