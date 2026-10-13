import json
import threading
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from app.errors import Cancelled

NUM_CTX = 8192
NUM_PREDICT = 4000
# The model stays loaded briefly after a draft (editing and regenerating are quick) and then frees
# its memory, so it does not compete with the user's other work.
KEEP_ALIVE = "1m"


class LLMError(Exception):
    """A failure with a stable `code` the UI turns into a plain-language message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class LLM(Protocol):
    def chat(self, system: str, user: str, schema: dict[str, Any], cancel: threading.Event) -> str:
        """Return the model's JSON answer, constrained to `schema`. Raises LLMError or Cancelled."""
        ...

    @property
    def model(self) -> str | None:
        """The model in use, read from the local settings (None when none is chosen)."""
        ...


class OllamaChat:
    """Talks to Ollama over its documented /api/chat endpoint, streaming so a cancel is quick."""

    def __init__(
        self,
        base_url: str,
        get_model: Callable[[], str | None],
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._get_model = get_model
        self._transport = transport  # tests inject a fake HTTP transport
        self._timeout = httpx.Timeout(connect=5, read=300, write=30, pool=5)

    @property
    def model(self) -> str | None:
        return self._get_model()

    def chat(self, system: str, user: str, schema: dict[str, Any], cancel: threading.Event) -> str:
        model = self._get_model()
        if not model:
            raise LLMError("llm_model_not_set")
        body: dict[str, Any] = {
            "model": model,
            "stream": True,
            "think": False,
            "format": schema,
            "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            try:
                return self._stream(body, cancel)
            except _ThinkingUnsupported:
                body.pop("think")  # models without a thinking switch reject the field
                return self._stream(body, cancel)
        except httpx.ConnectError as exc:
            raise LLMError("llm_unreachable") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("llm_timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMError("llm_failed") from exc

    def _stream(self, body: dict[str, Any], cancel: threading.Event) -> str:
        parts: list[str] = []
        with (
            httpx.Client(timeout=self._timeout, transport=self._transport) as client,
            client.stream("POST", f"{self._base_url}/api/chat", json=body) as response,
        ):
            if response.status_code >= 400:
                error = response.read().decode(errors="replace").lower()
                if response.status_code == 404 or "not found" in error:
                    raise LLMError("llm_model_missing")
                if response.status_code == 400 and "think" in body and "think" in error:
                    raise _ThinkingUnsupported
                raise LLMError("llm_failed")
            for line in response.iter_lines():
                if cancel.is_set():
                    raise Cancelled  # leaving the block closes the connection, which stops Ollama
                if not line:
                    continue
                data = json.loads(line)
                if "error" in data:
                    raise LLMError("llm_failed")
                parts.append(data.get("message", {}).get("content", ""))
                if data.get("done"):
                    break
        return "".join(parts)


class _ThinkingUnsupported(Exception):
    pass
