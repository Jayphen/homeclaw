"""Terminal REPL channel — runs the agent loop interactively in the terminal."""

from collections.abc import Callable
from typing import Any

from homeclaw.agent.loop import AgentLoop


async def run_repl(
    person: str,
    loop: AgentLoop,
    on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
) -> None:
    """Run an interactive REPL that feeds user input into the agent loop.

    Supports multiline input via ``\\`` continuation, and exits on
    ``exit``, ``quit``, or Ctrl-D (EOFError).
    """
    print(f"homeclaw — chatting as {person}")
    print("Type 'exit' or 'quit' to leave. Use \\ for multiline input.\n")

    while True:
        try:
            line = input(f"{person}> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        # Accumulate continuation lines
        lines: list[str] = [line]
        while lines[-1].endswith("\\"):
            lines[-1] = lines[-1][:-1]
            try:
                continuation = input("... ")
            except EOFError:
                break
            except KeyboardInterrupt:
                lines.clear()
                print()
                break
            lines.append(continuation)

        message = "\n".join(lines).strip()
        if not message:
            continue
        if message in ("exit", "quit"):
            break

        def _print_interim(text: str) -> None:
            print(f"\n  … {text}")

        loop.set_interim_callback(_print_interim)
        try:
            response = await loop.run(message, person)
        except KeyboardInterrupt:
            print("\n[interrupted]")
            continue

        print(f"\n---\n{response}\n")
