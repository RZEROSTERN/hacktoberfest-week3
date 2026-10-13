import json
import threading
from typing import Any

from app.errors import Cancelled
from app.llm import LLMError

PROFILE = {
    "name": "Ana Pérez (Studio Demo)",
    "services": ["Sitios web", "Sistemas de reservaciones"],
    "hourly_rate": "650 MXN por hora",
    "project_rates": ["Sitio web de hasta 5 secciones: 24,000 MXN"],
    "payment_terms": "50% de anticipo y 50% a la entrega.",
    "sections": [],
    "tone": "profesional y cercano",
}


class ScriptedLLM:
    """Returns canned answers in order. An Exception in the list is raised instead of returned."""

    def __init__(self, responses: list[str | Exception], model: str | None = "test-model") -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []  # (system, user) of each request
        self._model = model
        self.gate: threading.Event | None = None

    @property
    def model(self) -> str | None:
        return self._model

    def chat(self, system: str, user: str, schema: dict[str, Any], cancel: threading.Event) -> str:
        self.calls.append((system, user))
        if self.gate is not None:
            while not self.gate.wait(timeout=0.05):
                if cancel.is_set():
                    raise Cancelled
        if cancel.is_set():
            raise Cancelled
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def item(text: str, ids: list[int], *, assumption: bool = False) -> dict[str, Any]:
    return {"text": text, "segment_ids": ids, "assumption": assumption}


def note(text: str, ids: list[int]) -> dict[str, Any]:
    return {"text": text, "segment_ids": ids}


def notes_json(**overrides: Any) -> str:
    data: dict[str, Any] = {
        "client": "Kevin, pizzería Trevos",
        "client_context": [note("Tiene dos locales en Cancún", [0])],
        "problem": [note("Manejan el negocio por Facebook y tiene limitaciones", [1])],
        "goals": [note("Quieren un sistema en línea", [1])],
        "requirements": [note("Reservaciones sin mandar mensajes por Facebook", [2])],
        "constraints": [],
        "budget": [],
        "deadlines": [],
        "next_steps": [],
        "risks": [],
        "open_questions": [],
    }
    data.update(overrides)
    return json.dumps(data)


def draft_json(**overrides: Any) -> str:
    data: dict[str, Any] = {
        "summary": "Kevin necesita un sistema en línea para su pizzería.",
        "problem": "Hoy gestionan todo por Facebook y eso les limita.",
        "scope": [item("Reservaciones en línea", [2])],
        "deliverables": [item("Sistema de reservaciones", [2])],
        "out_of_scope": [],
        "timeline": "No se habló de fechas.",
        "open_questions": ["¿Quién proveerá las fotos?"],
    }
    data.update(overrides)
    return json.dumps(data)


def llm_error(code: str) -> LLMError:
    return LLMError(code)
