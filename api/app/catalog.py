"""The versioned list of models tested for the app (from docs/BENCHMARKS.md) and name checks."""

import re
from pathlib import Path

from pydantic import BaseModel


class WhisperModel(BaseModel):
    id: str
    title: str
    file: str
    url: str  # pinned to one revision of the model repository, so the checksum below always applies
    size_bytes: int
    sha256: str
    license: str
    note: str


class LlmModel(BaseModel):
    model: str  # the Ollama tag
    title: str
    recommended: bool
    size_bytes: int
    size_exact: bool  # false when the size is the rounded figure Ollama shows in its list
    ram_gb: int  # memory the computer should have; smaller computers see "not recommended"
    license: str
    note: str


class Catalog(BaseModel):
    version: int
    updated: str
    source: str
    whisper: WhisperModel
    llm: list[LlmModel]

    @property
    def recommended(self) -> LlmModel:
        return next(m for m in self.llm if m.recommended)

    def find(self, model: str) -> LlmModel | None:
        return next((m for m in self.llm if m.model == model), None)


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "models.json"


def load_catalog(path: Path | None = None) -> Catalog:
    return Catalog.model_validate_json((path or default_catalog_path()).read_text())


class ModelNameError(Exception):
    """A model name the app refuses before asking Ollama; `code` is a stable error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# [host/][namespace/]name[:tag], as in the Ollama library (e.g. `gemma4:e4b` or `user/model:q4`).
_NAME = re.compile(
    r"^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*){0,3}(:[a-z0-9][a-z0-9._-]*)?$", re.IGNORECASE
)
# Ollama's cloud models (`gemma4:cloud`, `qwen3-coder:480b-cloud`) run on its servers, not here.
_CLOUD = re.compile(r"(^|[-_.:/])cloud($|[-_.:/])", re.IGNORECASE)


def validate_model_name(name: str) -> str:
    """Return the cleaned name, or raise ModelNameError. Ollama checks that the model exists."""
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 200 or not _NAME.match(cleaned):
        raise ModelNameError("invalid_model_name")
    if _CLOUD.search(cleaned):
        raise ModelNameError("cloud_model")
    return cleaned
