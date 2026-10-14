"""Turns a finished transcript into call notes and a proposal draft with a language model.

Notes are extracted per time chunk and merged in code; the draft is written from the merged notes
and the freelancer's profile. Every model answer is validated (schema, sources, no prices) and
retried once with the problems listed before the job gives up with a clear error.
"""

import json
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app import drafting, i18n, notes
from app.errors import Cancelled
from app.llm import LLM, LLMError
from app.models import ACTIVE_DRAFT_STATUSES, Draft, DraftStatus, Profile, Segment
from app.notes import Line, Notes, Problem

# Only ids, statuses and counts are logged, never transcript, notes or proposal content.
log = logging.getLogger("postcall.generation")

NOTES_PROMPT = "notes_v3.md"
PROPOSAL_PROMPT = "proposal_v2.md"


class GenerationError(Exception):
    """A failure with a stable `code` the UI turns into a plain-language message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def default_prompts_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts"


def ask[M: BaseModel](
    llm: LLM,
    system: str,
    user: str,
    model_cls: type[M],
    validate: Callable[[M], list[Problem]],
    cancel: threading.Event,
) -> tuple[M, list[Problem]]:
    """Ask for JSON, validate it, and retry once with the problems listed.

    Returns the parsed answer and the problems that remain after the retry. Raises
    GenerationError("invalid_model_output") when no attempt produced valid JSON.
    """
    schema = model_cls.model_json_schema()
    prompt = f"{user}\n\nJSON schema of the answer:\n{json.dumps(schema)}"
    feedback: str | None = None
    best: tuple[M, list[Problem]] | None = None
    for _attempt in range(2):
        message = (
            prompt
            if feedback is None
            else f"{prompt}\n\nYour previous answer had problems. Fix them:\n{feedback}"
        )
        raw = llm.chat(system, message, schema, cancel)
        try:
            parsed = model_cls.model_validate_json(raw)
        except ValidationError as exc:
            first = exc.errors()[0]["msg"]
            feedback = f"- The answer did not match the schema (first error: {first})."
            continue
        problems = validate(parsed)
        if not problems:
            return parsed, []
        best = (parsed, problems)
        feedback = "\n".join(f"- {p.message}" for p in problems)
    if best is None:
        raise GenerationError("invalid_model_output")
    return best


class GenerationManager:
    """Runs one draft at a time on the shared worker thread."""

    def __init__(
        self,
        engine: Engine,
        llm: LLM,
        executor: ThreadPoolExecutor,
        prompts_dir: Path,
    ) -> None:
        self._engine = engine
        self._llm = llm
        self._executor = executor
        self._prompts_dir = prompts_dir
        self._cancels: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._stopping = False

    def recover(self) -> None:
        with Session(self._engine) as session:
            for draft in session.exec(
                select(Draft).where(col(Draft.status).in_(ACTIVE_DRAFT_STATUSES))
            ).all():
                draft.status = DraftStatus.FAILED
                draft.error_code = "interrupted"
                session.add(draft)
            session.commit()

    def is_active(self, call_id: str) -> bool:
        with self._lock:
            return call_id in self._cancels

    def submit(self, call_id: str) -> None:
        with self._lock:
            if call_id in self._cancels:
                return
            self._cancels[call_id] = threading.Event()
        self._executor.submit(self._run, call_id)

    def cancel(self, call_id: str) -> None:
        with self._lock:
            event = self._cancels.get(call_id)
        if event is not None:
            event.set()

    def stop(self) -> None:
        self._stopping = True
        with self._lock:
            for event in self._cancels.values():
                event.set()

    # -- job ---------------------------------------------------------------------------------

    def _run(self, call_id: str) -> None:
        with self._lock:
            cancel = self._cancels[call_id]
        try:
            self._execute(call_id, cancel)
        except Cancelled:
            if not self._stopping:
                self._update(call_id, status=DraftStatus.CANCELLED)
        except (GenerationError, LLMError) as exc:
            self._update(call_id, status=DraftStatus.FAILED, error_code=exc.code)
        except Exception:
            log.exception("unexpected failure in draft job %s", call_id)
            self._update(call_id, status=DraftStatus.FAILED, error_code="generation_failed")
        finally:
            with self._lock:
                self._cancels.pop(call_id, None)

    def _execute(self, call_id: str, cancel: threading.Event) -> None:
        with Session(self._engine) as session:
            draft = session.get(Draft, call_id)
            profile = session.get(Profile, 1)
            if draft is None:
                return
            language = draft.language
            segments = session.exec(
                select(Segment).where(Segment.call_id == call_id).order_by(col(Segment.idx))
            ).all()
            lines = [Line(s.idx, s.start, s.text) for s in segments]
        if profile is None:
            raise GenerationError("profile_missing")
        if not lines:
            raise GenerationError("empty_transcript")
        if cancel.is_set():
            raise Cancelled
        model = self._llm.model
        self._update(
            call_id,
            status=DraftStatus.EXTRACTING,
            progress=0.0,
            model=model,
            error_code=None,
            warnings=[],
        )

        warnings: list[str] = []
        merged = self._extract_notes(call_id, lines, cancel, warnings)
        if not notes.has_substance(merged):
            raise GenerationError("not_enough_information")
        self._update(
            call_id, status=DraftStatus.DRAFTING, notes=merged.model_dump(), stage_detail=None
        )
        proposal = self._draft(
            merged, profile, language, {line.idx for line in lines}, cancel, warnings
        )
        if cancel.is_set():
            raise Cancelled
        self._update(
            call_id,
            status=DraftStatus.DONE,
            progress=1.0,
            proposal=proposal.model_dump(),
            warnings=warnings,
        )

    def _extract_notes(
        self, call_id: str, lines: list[Line], cancel: threading.Event, warnings: list[str]
    ) -> Notes:
        system = self._prompt(NOTES_PROMPT)
        chunks = notes.chunk_lines(lines)
        parts: list[Notes] = []
        dropped_total = 0
        for number, chunk in enumerate(chunks, start=1):
            self._update(
                call_id,
                progress=(number - 1) / (len(chunks) + 1),
                stage_detail=f"{number}/{len(chunks)}",
            )
            valid_ids = {line.idx for line in chunk}

            def validate_notes(n: Notes, ids: set[int] = valid_ids) -> list[Problem]:
                return notes.check_notes(n, ids)

            parsed, problems = ask(
                self._llm,
                system,
                f"Transcript:\n{notes.format_chunk(chunk)}",
                Notes,
                validate_notes,
                cancel,
            )
            if problems:
                parsed, dropped = notes.repair_notes(parsed, valid_ids)
                dropped_total += dropped
            parts.append(parsed)
        if dropped_total:
            warnings.append(f"dropped_unsourced_notes:{dropped_total}")
        return notes.merge_notes(parts)

    def _draft(
        self,
        call_notes: Notes,
        profile: Profile,
        language: str,
        valid_ids: set[int],
        cancel: threading.Event,
        warnings: list[str],
    ) -> drafting.ProposalDraft:
        system = self._prompt(PROPOSAL_PROMPT).replace("{language}", i18n.language_name(language))
        freelancer: dict[str, Any] = {
            "name": profile.name,
            "services": profile.services,
            "tone": profile.tone,
        }
        notes_json = json.dumps(drafting.notes_for_model(call_notes), ensure_ascii=False)
        freelancer_json = json.dumps(freelancer, ensure_ascii=False)
        user = f"Call notes:\n{notes_json}\n\nFreelancer:\n{freelancer_json}"

        def validate_draft(d: drafting.DraftOut) -> list[Problem]:
            return drafting.check_draft(d, valid_ids)

        parsed, problems = ask(
            self._llm,
            system,
            user,
            drafting.DraftOut,
            lambda d: drafting.check_draft(d, valid_ids),
            cancel,
        )
        if any(p.hard for p in problems):
            raise GenerationError("draft_invalid")
        parsed, removed, flagged = drafting.repair_draft(parsed, valid_ids)
        if removed:
            warnings.append(f"removed_unknown_sources:{removed}")
        if flagged:
            warnings.append(f"flagged_assumptions:{flagged}")
        return drafting.assemble(parsed, call_notes, profile, language)

    def _prompt(self, name: str) -> str:
        return (self._prompts_dir / name).read_text()

    def _update(self, call_id: str, **fields: object) -> None:
        with Session(self._engine) as session:
            draft = session.get(Draft, call_id)
            if draft is None:
                return
            for key, value in fields.items():
                setattr(draft, key, value)
            draft.updated_at = datetime.now(UTC)
            session.add(draft)
            session.commit()
