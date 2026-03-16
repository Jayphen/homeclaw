"""CLI entry point — ``homeclaw chat`` starts the REPL."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


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
    # For dry-run we don't need a valid API key — build context without an LLM call.
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
    from homeclaw.agent.loop import AgentLoop
    from homeclaw.agent.providers.factory import create_provider
    from homeclaw.agent.tools import ToolRegistry, register_builtin_tools
    from homeclaw.channel.repl import run_repl
    from homeclaw.config import HomeclawConfig

    config = HomeclawConfig()
    provider = create_provider(config)

    registry = ToolRegistry()
    if not args.no_tools:
        register_builtin_tools(registry, workspaces)

    loop = AgentLoop(
        provider=provider,
        registry=registry,
        workspaces=workspaces,
        on_tool_call=_print_tool_call,
    )

    asyncio.run(run_repl(person=args.person, loop=loop, on_tool_call=_print_tool_call))


def _run_telegram() -> None:
    """Load config, create provider + loop, and start the Telegram bot."""
    from homeclaw.agent.loop import AgentLoop
    from homeclaw.agent.providers.factory import create_provider
    from homeclaw.agent.tools import ToolRegistry, register_builtin_tools
    from homeclaw.channel.telegram import TelegramChannel
    from homeclaw.config import HomeclawConfig

    config = HomeclawConfig()

    if not config.telegram_token:
        print("Error: TELEGRAM_TOKEN not set. Set it in .env or as an environment variable.")
        sys.exit(1)

    workspaces = config.workspaces.resolve()
    provider = create_provider(config)

    registry = ToolRegistry()
    register_builtin_tools(registry, workspaces)

    loop = AgentLoop(
        provider=provider,
        registry=registry,
        workspaces=workspaces,
        on_tool_call=_print_tool_call,
    )

    channel = TelegramChannel(
        token=config.telegram_token,
        loop=loop,
        workspaces=workspaces,
    )
    channel.run()
