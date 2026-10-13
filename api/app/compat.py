"""The compatibility check: can this model do the app's real task?

A short built-in call goes through the same notes extraction the app uses. The model passes when it
returns valid structured notes with real sources and finds something to build a proposal on. Any
chat model can produce valid JSON when the output is constrained, so the last condition is what
catches models that are too small or built for something else.
"""

import threading
from pathlib import Path
from typing import Protocol

import httpx

from app.generation import NOTES_PROMPT, GenerationError, ask
from app.llm import LLMError, OllamaChat
from app.notes import Line, Notes, Problem, check_notes, format_chunk, has_substance, repair_notes

# The expected answer is a few hundred tokens: a model that rambles past this is failing the test.
CHECK_MAX_TOKENS = 1200

SAMPLE = [
    "Hi, thanks for taking the time. Can you tell me about your business?",
    "Sure, we run a small bakery with two shops in Guadalajara.",
    "What problem are you trying to solve?",
    "Right now customers order by phone and we lose orders when we are busy.",
    "We need a website where people can order online and pick up at the shop.",
    "It should show our menu with photos and let customers choose a pickup time.",
    "We don't need delivery for now, only pickup.",
    "I will send you a first design in two weeks.",
]


class CompatError(Exception):
    """The model failed the check; `code` is a stable error code for the UI."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CompatChecker(Protocol):
    def check(self, model: str, cancel: threading.Event) -> None:
        """Return normally when the model passes; raise CompatError (or Cancelled) otherwise."""
        ...


_LLM_CODES = {
    "llm_model_missing": "compat_model_missing",
    "llm_unreachable": "ollama_unreachable",
    "llm_timeout": "compat_timeout",
}


class OllamaCompatChecker:
    def __init__(
        self, ollama_url: str, prompts_dir: Path, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._url = ollama_url
        self._prompts_dir = prompts_dir
        self._transport = transport

    def check(self, model: str, cancel: threading.Event) -> None:
        llm = OllamaChat(self._url, lambda: model, self._transport, num_predict=CHECK_MAX_TOKENS)
        lines = [Line(i, i * 5.0, text) for i, text in enumerate(SAMPLE)]
        ids = {line.idx for line in lines}

        def validate(notes: Notes) -> list[Problem]:
            return check_notes(notes, ids)

        system = (self._prompts_dir / NOTES_PROMPT).read_text()
        try:
            parsed, _ = ask(
                llm, system, f"Transcript:\n{format_chunk(lines)}", Notes, validate, cancel
            )
        except LLMError as exc:
            raise CompatError(_LLM_CODES.get(exc.code, "compat_no_chat")) from exc
        except GenerationError as exc:
            raise CompatError("compat_invalid_output") from exc
        repaired, _ = repair_notes(parsed, ids)
        if not has_substance(repaired):
            raise CompatError("compat_not_enough")
