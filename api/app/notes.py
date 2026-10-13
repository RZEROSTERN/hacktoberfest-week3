"""Call notes: what the language model extracts from the transcript, with the segments it cites."""

import re
from dataclasses import dataclass

from pydantic import BaseModel

CHUNK_SECONDS = 480  # about 8 minutes of speech per model call


class NoteItem(BaseModel):
    text: str
    segment_ids: list[int]


class Notes(BaseModel):
    client: str
    client_context: list[NoteItem]
    problem: list[NoteItem]
    goals: list[NoteItem]
    requirements: list[NoteItem]
    constraints: list[NoteItem]
    budget: list[NoteItem]
    deadlines: list[NoteItem]
    next_steps: list[NoteItem]
    risks: list[NoteItem]
    open_questions: list[str]


# Every list of sourced items in the notes. Derived from the model so that a new group cannot be
# forgotten by the merge, source check and repair code.
GROUPS = [
    name for name, field in Notes.model_fields.items() if name not in ("client", "open_questions")
]


@dataclass(frozen=True)
class Line:
    """A transcript segment as the model sees it. `idx` is the segment id used as a source."""

    idx: int
    start: float
    text: str


@dataclass(frozen=True)
class Problem:
    message: str
    hard: bool = False  # hard problems cannot be repaired in code


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def chunk_lines(lines: list[Line], seconds: float = CHUNK_SECONDS) -> list[list[Line]]:
    """Split the transcript by time, always on a segment boundary."""
    chunks: list[list[Line]] = []
    for line in lines:
        if not chunks or line.start - chunks[-1][0].start >= seconds:
            chunks.append([])
        chunks[-1].append(line)
    return chunks


def format_chunk(chunk: list[Line]) -> str:
    return "\n".join(f"[S{line.idx} @ {line.start:.0f}s] {line.text}" for line in chunk)


def check_notes(notes: Notes, valid_ids: set[int]) -> list[Problem]:
    problems = []
    for group in GROUPS:
        for item in getattr(notes, group):
            bad = [i for i in item.segment_ids if i not in valid_ids]
            if not item.segment_ids or bad:
                problems.append(
                    Problem(
                        f"In '{group}', the item starting \"{item.text[:60]}\" must cite "
                        "segment ids "
                        f"from {min(valid_ids)} to {max(valid_ids)} only"
                        + (f" (these are not valid: {bad})" if bad else " (it cites none)")
                    )
                )
    return problems


def repair_notes(notes: Notes, valid_ids: set[int]) -> tuple[Notes, int]:
    """Keep valid sources only; drop items left with none. Returns (notes, dropped)."""
    dropped = 0
    fixed = notes.model_copy(deep=True)
    for group in GROUPS:
        kept = []
        for item in getattr(fixed, group):
            item.segment_ids = sorted({i for i in item.segment_ids if i in valid_ids})
            if item.segment_ids and item.text.strip():
                kept.append(item)
            else:
                dropped += 1
        setattr(fixed, group, kept)
    return fixed, dropped


def merge_notes(parts: list[Notes]) -> Notes:
    """Combine the notes of every chunk, joining items that say the same thing."""
    merged = Notes(
        client=next((p.client for p in parts if p.client.strip()), ""),
        client_context=[],
        problem=[],
        goals=[],
        requirements=[],
        constraints=[],
        budget=[],
        deadlines=[],
        next_steps=[],
        risks=[],
        open_questions=[],
    )
    for group in GROUPS:
        by_text: dict[str, NoteItem] = {}
        for part in parts:
            for item in getattr(part, group):
                key = normalize(item.text)
                if key in by_text:
                    by_text[key].segment_ids = sorted(
                        {*by_text[key].segment_ids, *item.segment_ids}
                    )
                else:
                    by_text[key] = item.model_copy(deep=True)
        setattr(merged, group, list(by_text.values()))
    seen: set[str] = set()
    for part in parts:
        for question in part.open_questions:
            if question.strip() and normalize(question) not in seen:
                seen.add(normalize(question))
                merged.open_questions.append(question.strip())
    return merged


def has_substance(notes: Notes) -> bool:
    """False when the call gave nothing a proposal could be built on."""
    return bool(notes.problem or notes.goals or notes.requirements)
