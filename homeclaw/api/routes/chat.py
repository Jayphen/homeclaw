"""Chat API route — streaming endpoint for web UI chat.

Streams the agent response as plain text, compatible with the Vercel AI SDK's
``TextStreamChatTransport`` (used by ``@ai-sdk/svelte``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from homeclaw.api.deps import get_agent_loop, get_current_member

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _extract_text(message: dict[str, Any]) -> str:
    """Extract plain text from an AI SDK message (parts-based or legacy)."""
    # AI SDK v6: messages have a `parts` array
    if "parts" in message:
        return " ".join(
            part.get("text", "")
            for part in message["parts"]
            if isinstance(part, dict) and part.get("type") == "text"
        ).strip()
    # Legacy / simple: plain `content` string
    return (message.get("content") or "").strip()


@router.post("")
async def chat(request: Request) -> StreamingResponse:
    """Handle a chat message and stream the response as plain text."""
    member = await get_current_member(request)
    loop = get_agent_loop()
    if loop is None:
        raise HTTPException(503, "Agent not ready — configure a provider first")

    body = await request.json()
    messages: list[dict[str, Any]] = body.get("messages", [])

    # Extract the last user message (the Chat class sends the full history)
    last_user: dict[str, Any] | None = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user = msg
            break

    if not last_user:
        raise HTTPException(400, "No user message found")

    content = _extract_text(last_user)
    if not content:
        raise HTTPException(400, "Empty message")

    person = member or "user"

    async def generate():
        interim_q: asyncio.Queue[str] = asyncio.Queue()
        has_interim = False

        async def _on_interim(text: str) -> None:
            await interim_q.put(text)

        result_task = asyncio.create_task(
            loop.run(content, person, interim_callback=_on_interim),
        )

        try:
            # Stream interim status messages as italic text while the loop runs
            while not result_task.done():
                try:
                    interim = await asyncio.wait_for(
                        interim_q.get(), timeout=0.3,
                    )
                    has_interim = True
                    yield f"*{interim}*\n"
                except TimeoutError:
                    continue

            # Drain any remaining interim messages
            while not interim_q.empty():
                interim = interim_q.get_nowait()
                has_interim = True
                yield f"*{interim}*\n"

            response = await result_task

            # Separate interim status from the response
            if has_interim:
                yield "\n"

            yield response

        except Exception as exc:
            logger.exception("Chat error for %s", person)
            error_msg = str(exc)
            if len(error_msg) > 300:
                error_msg = error_msg[:300] + "..."
            yield f"Sorry, something went wrong: {error_msg}"

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
    )
