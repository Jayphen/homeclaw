"""Tests for the OpenAI-compatible provider adapter."""

from openai.types.chat import ChatCompletion

from homeclaw.agent.providers.base import Message, ToolCall
from homeclaw.agent.providers.openai import _parse_response, _to_api_message


def test_to_api_message_preserves_tool_call_thought_signature() -> None:
    """Gemini-compatible tool-call signatures must survive round-trips."""
    message = Message(
        role="assistant",
        content="",
        tool_calls=[
            ToolCall(
                id="call_1",
                name="budget__db_query",
                arguments={"sql": "select 1"},
                thought_signature="SIG_A",
            ),
            ToolCall(
                id="call_2",
                name="budget__db_query",
                arguments={"sql": "select 2"},
            ),
        ],
    )

    api_message = _to_api_message(message)

    assert api_message["tool_calls"][0]["thought_signature"] == "SIG_A"
    assert "thought_signature" not in api_message["tool_calls"][1]


def test_parse_response_reads_tool_call_thought_signature() -> None:
    """Unknown Gemini tool-call fields should be recovered from the SDK model."""
    response = ChatCompletion.model_validate(
        {
            "id": "resp_1",
            "object": "chat.completion",
            "created": 0,
            "model": "gemini-flash-latest",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "budget__db_query",
                                    "arguments": '{"sql":"select 1"}',
                                },
                                "thought_signature": "SIG_A",
                            }
                        ],
                    },
                }
            ],
            "usage": {
                "completion_tokens": 1,
                "prompt_tokens": 1,
                "total_tokens": 2,
            },
        }
    )

    parsed = _parse_response(response)

    assert parsed.stop_reason == "tool_use"
    assert parsed.tool_calls[0].thought_signature == "SIG_A"
