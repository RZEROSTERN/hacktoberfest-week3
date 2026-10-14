import json
import threading
from typing import Any

import httpx
import pytest

from app.errors import Cancelled
from app.llm import LLMError, OllamaChat

SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}}


def ndjson(*contents: str) -> bytes:
    lines = [{"message": {"content": c}, "done": False} for c in contents]
    lines.append({"message": {"content": ""}, "done": True})
    return "\n".join(json.dumps(line) for line in lines).encode()


def chat_with(handler: Any, model: str | None = "some-model") -> OllamaChat:
    return OllamaChat("http://ollama.test/", lambda: model, transport=httpx.MockTransport(handler))


def test_streams_the_answer_and_sends_the_documented_request() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://ollama.test/api/chat"
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=ndjson('{"a":', ' "hi"}'))

    answer = chat_with(handler).chat("sys", "user", SCHEMA, threading.Event())
    assert answer == '{"a": "hi"}'
    body = seen[0]
    assert body["model"] == "some-model"  # comes from the getter, never from a constant
    assert body["format"] == SCHEMA
    assert body["think"] is False
    assert body["stream"] is True
    assert body["options"]["temperature"] == 0
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]


def test_no_model_selected() -> None:
    chat = chat_with(lambda r: httpx.Response(200), model=None)
    with pytest.raises(LLMError) as err:
        chat.chat("s", "u", SCHEMA, threading.Event())
    assert err.value.code == "llm_model_not_set"


def test_unknown_model_is_reported() -> None:
    chat = chat_with(lambda r: httpx.Response(404, json={"error": "model 'x' not found"}))
    with pytest.raises(LLMError) as err:
        chat.chat("s", "u", SCHEMA, threading.Event())
    assert err.value.code == "llm_model_missing"


def test_ollama_not_running() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMError) as err:
        chat_with(handler).chat("s", "u", SCHEMA, threading.Event())
    assert err.value.code == "llm_unreachable"


def test_models_without_a_thinking_switch_are_retried_without_it() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if "think" in body:
            return httpx.Response(400, json={"error": "this model does not support think"})
        return httpx.Response(200, content=ndjson("{}"))

    assert chat_with(handler).chat("s", "u", SCHEMA, threading.Event()) == "{}"
    assert "think" in bodies[0] and "think" not in bodies[1]


def test_error_line_in_the_stream() -> None:
    chat = chat_with(lambda r: httpx.Response(200, content=b'{"error": "boom"}'))
    with pytest.raises(LLMError) as err:
        chat.chat("s", "u", SCHEMA, threading.Event())
    assert err.value.code == "llm_failed"


def test_cancel_stops_reading_the_stream() -> None:
    cancel = threading.Event()
    cancel.set()
    chat = chat_with(lambda r: httpx.Response(200, content=ndjson("a", "b")))
    with pytest.raises(Cancelled):
        chat.chat("s", "u", SCHEMA, cancel)
